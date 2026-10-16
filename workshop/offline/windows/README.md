# Шаблоны Windows USB-комплекта

Эти файлы копируются в **корень Windows-комплекта**, рядом с `qai-participant.zip`, `installers/`, `tools/`,
`python-wheels/`, `images/` и `USB-MANIFEST.json`. Не запускайте setup.sh прямо из этой папки исходников.

Маршрут: [Windows offline](../../../docs/new-windows-offline.md).
Сборка зависимостей выполняется ведущим отдельно, а не на ноутбуке участника.
Установщики/образы/rootfs не хранятся в Git. Комплект содержит Ubuntu 24.04 x64 с Python 3.12,
39 matching wheels и 23 amd64 образа; runtime installer не скачивает зависимости.
