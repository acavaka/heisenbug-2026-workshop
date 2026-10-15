// Copyright 2023 Google LLC
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//      http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

package main

import (
	"context"
	"os"
	"strconv"
	"strings"
	"sync"
	"time"

	pb "github.com/GoogleCloudPlatform/microservices-demo/src/productcatalogservice/genproto"
	"google.golang.org/grpc/codes"
	healthpb "google.golang.org/grpc/health/grpc_health_v1"
	"google.golang.org/grpc/status"
)

// BUG-1024 workshop plant:
// GetProduct serves prices from a TTL cache and does NOT invalidate on UpdateProductPrice.
// ListProducts always reads the live in-memory catalog (used by product detail page).
// Cart/checkout keep calling GetProduct → stale price until TTL expires.

const defaultPriceCacheTTL = 3600 * time.Second

type priceCacheEntry struct {
	product   *pb.Product
	expiresAt time.Time
}

type productCatalog struct {
	catalog    pb.ListProductsResponse
	priceCache map[string]priceCacheEntry
	cacheMu    sync.RWMutex
	cacheTTL   time.Duration
}

func newProductCatalog() *productCatalog {
	ttl := defaultPriceCacheTTL
	if s := os.Getenv("PRICE_CACHE_TTL_SECONDS"); s != "" {
		if n, err := strconv.Atoi(s); err == nil && n > 0 {
			ttl = time.Duration(n) * time.Second
		}
	}
	return &productCatalog{
		priceCache: make(map[string]priceCacheEntry),
		cacheTTL:   ttl,
	}
}

func (p *productCatalog) Check(ctx context.Context, req *healthpb.HealthCheckRequest) (*healthpb.HealthCheckResponse, error) {
	return &healthpb.HealthCheckResponse{Status: healthpb.HealthCheckResponse_SERVING}, nil
}

func (p *productCatalog) Watch(req *healthpb.HealthCheckRequest, ws healthpb.Health_WatchServer) error {
	return status.Errorf(codes.Unimplemented, "health check via Watch not implemented")
}

func (p *productCatalog) ListProducts(context.Context, *pb.Empty) (*pb.ListProductsResponse, error) {
	time.Sleep(extraLatency)
	// Intentionally bypass price cache — home / product display use this path.
	return &pb.ListProductsResponse{Products: p.parseCatalog()}, nil
}

func (p *productCatalog) GetProduct(ctx context.Context, req *pb.GetProductRequest) (*pb.Product, error) {
	time.Sleep(extraLatency)

	p.cacheMu.RLock()
	if entry, ok := p.priceCache[req.Id]; ok && time.Now().Before(entry.expiresAt) {
		age := time.Since(entry.expiresAt.Add(-p.cacheTTL)).Seconds()
		p.cacheMu.RUnlock()
		log.Infof("cache hit product_id=%s price_units=%d price_nanos=%d age_s=%.0f",
			req.Id, entry.product.PriceUsd.GetUnits(), entry.product.PriceUsd.GetNanos(), age)
		return cloneProduct(entry.product), nil
	}
	p.cacheMu.RUnlock()

	found := p.findProduct(req.Id)
	if found == nil {
		return nil, status.Errorf(codes.NotFound, "no product with ID %s", req.Id)
	}

	cloned := cloneProduct(found)
	p.cacheMu.Lock()
	p.priceCache[req.Id] = priceCacheEntry{
		product:   cloneProduct(found),
		expiresAt: time.Now().Add(p.cacheTTL),
	}
	p.cacheMu.Unlock()

	log.Infof("cache miss product_id=%s fetched price_units=%d price_nanos=%d ttl_s=%.0f",
		req.Id, cloned.PriceUsd.GetUnits(), cloned.PriceUsd.GetNanos(), p.cacheTTL.Seconds())
	return cloned, nil
}

func (p *productCatalog) SearchProducts(ctx context.Context, req *pb.SearchProductsRequest) (*pb.SearchProductsResponse, error) {
	time.Sleep(extraLatency)

	var ps []*pb.Product
	for _, product := range p.parseCatalog() {
		if strings.Contains(strings.ToLower(product.Name), strings.ToLower(req.Query)) ||
			strings.Contains(strings.ToLower(product.Description), strings.ToLower(req.Query)) {
			ps = append(ps, product)
		}
	}

	return &pb.SearchProductsResponse{Results: ps}, nil
}

func (p *productCatalog) findProduct(id string) *pb.Product {
	for _, prod := range p.parseCatalog() {
		if prod.Id == id {
			return prod
		}
	}
	return nil
}

// UpdateProductPrice mutates the live catalog but intentionally does NOT invalidate priceCache.
func (p *productCatalog) UpdateProductPrice(id string, units int64, nanos int32) (*pb.Product, error) {
	catalogMutex.Lock()
	defer catalogMutex.Unlock()

	var found *pb.Product
	for _, prod := range p.catalog.Products {
		if prod.Id == id {
			found = prod
			break
		}
	}
	if found == nil {
		return nil, status.Errorf(codes.NotFound, "no product with ID %s", id)
	}

	oldUnits, oldNanos := found.PriceUsd.GetUnits(), found.PriceUsd.GetNanos()
	if found.PriceUsd == nil {
		found.PriceUsd = &pb.Money{CurrencyCode: "USD"}
	}
	found.PriceUsd.Units = units
	found.PriceUsd.Nanos = nanos

	log.Infof("shopapi.admin price updated product_id=%s old_units=%d old_nanos=%d new_units=%d new_nanos=%d (cache NOT invalidated)",
		id, oldUnits, oldNanos, units, nanos)
	return cloneProduct(found), nil
}

func (p *productCatalog) parseCatalog() []*pb.Product {
	if reloadCatalog || len(p.catalog.Products) == 0 {
		err := loadCatalog(&p.catalog)
		if err != nil {
			return []*pb.Product{}
		}
	}

	return p.catalog.Products
}

func cloneProduct(in *pb.Product) *pb.Product {
	if in == nil {
		return nil
	}
	out := *in
	if in.PriceUsd != nil {
		price := *in.PriceUsd
		out.PriceUsd = &price
	}
	if in.Categories != nil {
		cats := make([]string, len(in.Categories))
		copy(cats, in.Categories)
		out.Categories = cats
	}
	return &out
}
