"""
Объявление всех объектов
"""

import builtins
import gzip
import json
# -- импорт библиотек
import pathlib
import secrets
import time
from pathlib import Path


# -- объявление классов
class Object:
    def __init__(self, identity=None, scripts=None, children=None, world=None, parent=None):
        if identity is None:
            identity = secrets.token_urlsafe(16)
        if scripts is None:
            scripts = []
        if children is None:
            children = []

        self.identity = identity
        self.scripts = scripts
        self.children = children
        self.attributes = {}
        self.connection = None

        # -- знание о мире и родителе
        self.world = world
        self.parent = parent

        # -- обработчик скриптов
        self.listeners = {}

        self.alive = True
        self._pending_tasks = []

    def save(self):
        return {
            'identity': self.identity,
            'scripts': [script.identity for script in self.scripts],
            'children': [child.save() for child in self.children],
            'attributes': self.attributes
        }

    def load(self, saved, world):
        self.identity = saved['identity']
        self.world = world
        self.scripts = [world.do_get_script_by_identity(i) for i in saved['scripts']]
        self.children = [Object(world=world, parent=self).load(child, world) for child in saved['children']]
        self.attributes = saved['attributes']
        self.compile_scripts()
        return self

    def load_from_prefab(self, prefab):
        self.scripts = prefab.scripts
        self.children = []
        for child_prefab in prefab.children:
            child = child_prefab.instance()
            child.parent = self
            self.children.append(child)
        self.attributes = prefab.attributes
        self.compile_scripts()
        return self

    # - быстрые макросы
    def add_child(self):
        self.children.append(Object(world=self.world, parent=self))

    def adopt(self, object):
        if object.parent:
            object.parent.delete_child_by_identity(object.identity)
        object.world = self.world
        object.parent = self
        self.children.append(object)

    def delete_child_by_identity(self, identity):
        for child_indx in range(len(self.children)):
            if self.children[child_indx].identity == identity:
                child = self.children.pop(child_indx)
                child.parent = None
                return

    def get_name(self):
        if 'name' in self.attributes:
            try:
                return str(self.attributes['name'])
            except Exception as e:
                return self.identity
        else:
            return self.identity

    def send(self, message):
        if not self.alive:
            return
        if self.connection:
            try:
                self.connection.send(message)
            except Exception:
                pass

    def trigger(self, event, *args, **kwargs):
        if not self.alive:
            return
        if event in self.listeners:
            for listener in list(self.listeners[event]):
                listener(*args, **kwargs)

    def on_event(self, event_type):
        def decorator(func):
            if event_type not in self.listeners:
                self.listeners[event_type] = []
            self.listeners[event_type].append(func)
            return func

        return decorator

    def compile_scripts(self):
        for script in self.scripts:
            script.compile(self)

    def die(self):
        if not self.alive:
            return
        self.trigger('on_die')
        self.alive = False
        for task in list(self._pending_tasks):
            if task in self.world.scheduled:
                self.world.scheduled.remove(task)
        self._pending_tasks.clear()
        for child in list(self.children):
            child.die()
        self.children = []
        if self.parent:
            self.parent.delete_child_by_identity(self.identity)
        self.parent = None
        self.connection = None
        self.listeners = {}


class Prefab(Object):
    def instance(self):
        object = Object(world=self.world).load_from_prefab(self)
        object.trigger('on_spawn')
        return object


class Script:
    def __init__(self, code=None, name=None, identity=None, world=None):
        if identity is None:
            identity = secrets.token_urlsafe(16)
        if code is None:
            code = f'# Скрипт с идентификатором {identity} \n'
        if name is None:
            name = f'Скрипт {identity[:4]}...'

        self.code = code
        self.name = name
        self.identity = identity
        self.world = world
        self.namespaces = {}

    def save(self):
        return {
            'code': self.code,
            'name': self.name,
            'identity': self.identity
        }

    def load(self, saved):
        self.code = saved['code']
        self.name = saved['name']
        self.identity = saved['identity']

        return self

    def compile(self, object):
        self.namespaces[object.identity] = {}
        exec(self.code,
             {'self': object, '__builtins__': builtins, 'world': self.world, 'script': self},
             self.namespaces[object.identity])


class World:
    def __init__(self):
        self._data = {}

        self.filename = None
        self.root_object = None
        self.prefabs = None
        self.scripts = None
        self.port_wss = None
        self.port_web = None
        self.connection_prefab_identity = None
        self.web_client_code = ''

        # -- атрибуты, относящиеся только к игре
        self.started = False
        self.scheduled = []
        self.last_tick_time = time.time()
        self.listeners = {}

        self.load_new()

    # - функции загрузки
    def load_filename(self, filename: Path):
        self.filename = filename.resolve()

        with gzip.open(filename, 'rt', encoding='UTF-8') as file:
            self._data = json.load(file)

        self.scripts = [Script(world=self).load(script) for script in self._data['scripts']]
        self.root_object = Object(world=self).load(self._data['root'], self)
        self.prefabs = [Prefab(world=self).load(prefab, self) for prefab in self._data['prefabs']]
        self.port_wss = self._data['server']['port_wss']
        self.port_web = self._data['server']['port_web']
        self.filename = filename
        self.connection_prefab_identity = self._data['connection_prefab_identity']
        self.web_client_code = self._data['server']['web_client_code']

        return self

    def load_new(self):
        self.filename = pathlib.Path(__file__).parent.absolute() / 'world.wrld'
        self.root_object = Object(world=self)
        self.prefabs = []
        self.scripts = []
        self.port_wss = 1337
        self.port_web = 1339
        self.connection_prefab_identity = ''
        self.web_client_code = ''

        return self

    # - функции сохранения
    def save_filename(self, filename: Path):
        self._data = {
            'root': self.root_object.save(),
            'prefabs': [prefab.save() for prefab in self.prefabs],
            'scripts': [script.save() for script in self.scripts],
            'connection_prefab_identity': self.connection_prefab_identity,
            'server': {
                'port_wss': self.port_wss,
                'port_web': self.port_web,
                'web_client_code': self.web_client_code
            },
        }

        with gzip.open(filename, 'wt', encoding='UTF-8', compresslevel=9) as file:
            json.dump(self._data, file)

    # - быстрые макросы
    def do_new_script(self):
        self.scripts.append(Script(world=self))

    def do_delete_script(self, identity):
        for script_indx in range(len(self.scripts)):
            if self.scripts[script_indx].identity == identity:
                del self.scripts[script_indx]
                break

    def do_get_script_by_identity(self, identity):
        for script in self.scripts:
            if script.identity == identity:
                return script

    def do_get_prefab_by_identity(self, identity):
        for prefab in self.prefabs:
            found = self.find_in_children(prefab, identity)
            if found is not None:
                return found
        return None

    def do_get_object_by_identity(self, identity):
        return self.find_in_children(self.root_object, identity)

    def find_in_children(self, obj, target_identity):
        if obj.identity == target_identity:
            return obj
        for child in obj.children:
            found = self.find_in_children(child, target_identity)
            if found is not None:
                return found
        return None

    def get_objects_from_root(self, object):
        found = [object]
        for child in object.children:
            found += self.get_objects_from_root(child)
        return found

    def get_objects(self):
        return self.get_objects_from_root(self.root_object)

    # -- игровая логика
    def connect(self, connection):
        connection_prefab = self.do_get_prefab_by_identity(self.connection_prefab_identity).instance()

        connection.connected_object = connection_prefab
        connection_prefab.connection = connection

        self.root_object.adopt(connection_prefab)

    def start(self):
        self.started = True
        self.last_tick_time = time.time()

    def on_schedule(self, time, *args, **kwargs):
        def decorator(func):
            self.scheduled.append([time, func, args, kwargs])
            return func

        return decorator

    def schedule(self, func, time, *args, **kwargs):
        self.scheduled.append([time, func, args, kwargs])

    def trigger(self, event, *args, **kwargs):
        if event in self.listeners:
            for listener in self.listeners[event]:
                listener.__call__(*args, **kwargs)

    def on_event(self, event_type):
        def decorator(func):
            if event_type not in self.listeners:
                self.listeners[event_type] = []
            self.listeners[event_type].append(func)
            return func

        return decorator

    def tick(self):
        current_time = time.time()
        delta_time = current_time - self.last_tick_time
        self.last_tick_time = current_time

        for task in self.scheduled[:]:
            task[0] -= delta_time
            if task[0] > 0:
                continue

            func = task[1]
            owner = getattr(func, '__self__', None)

            if isinstance(owner, Object) and not owner.alive:
                if task in self.scheduled:
                    self.scheduled.remove(task)
                continue

            if len(task) > 4 and isinstance(task[4], Object) and not task[4].alive:
                if task in self.scheduled:
                    self.scheduled.remove(task)
                continue

            try:
                func(*task[2], **task[3])
            except Exception as e:
                print(f"Error in scheduled task: {e}")

            if task in self.scheduled:
                self.scheduled.remove(task)