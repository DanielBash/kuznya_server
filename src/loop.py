def game_loop(world):
    from utils import network

    print("[СЕРВЕР] Запуск сервера.")

    world.start()

    while True:
        network.ws_manager.update()

        for conn in network.ws_manager.connections:
            messages = conn.get_messages()
            for message in messages:
                conn.connected_object.trigger('on_message', message)

        world.tick()


def run():
    from main import world

    try:
        game_loop(world)
    except KeyboardInterrupt:
        print("\n[СЕРВЕР] Выключение сервера.")