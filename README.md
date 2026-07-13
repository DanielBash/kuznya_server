# КУЗНЯ: СЕРВЕР

> Интерпретатор кода мира и сервер КУЗНИ. Запуск telnet/ssh/web серверов.

См. репозиторий [редактора](https://github.com/DanielBash/kuznya) миров.

## Запуск сервера(debain)

### Запуск через скрипт-установщик(debain)

1) **Скачайте и запустите установочный скрипт**
```bash
bash <(curl -s https://raw.githubusercontent.com/DanielBash/kuznya/main/install.sh)
```

### Установка вручную(debain)
1) **Скачайте официальный репозиторий и перейдите в него**
```bash
git clone https://github.com/DanielBash/kuznya_server.git
cd kuznya_server
```

2) **Установите зависимости и запустите среду разработки**
```bash
pip install -r requirements.txt
cd src
python main.py <world-file-path>
```