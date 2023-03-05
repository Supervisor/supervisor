import sys

if sys.version_info >= (3, 9):
    from importlib.resources import files


    def read_text(package, path):
        return files(package).joinpath(path).read_text(encoding='utf-8')


    def find(package, path):
        return str(files(package).joinpath(path))

elif sys.version_info >= (3, 7):
    import importlib.resources


    def read_text(package, path):
        with importlib.resources.path(package, '__init__.py') as p:
            return p.parent.joinpath(path).read_text(encoding='utf-8')


    def find(package, path):
        with importlib.resources.path(package, '__init__.py') as p:
            return str(p.parent.joinpath(path))

else:
    from io import open

    import importlib_resources


    def read_text(package, path):
        with open(find(package, path), 'r', encoding='utf-8') as f:
            return f.read()


    def find(package, path):
        with importlib_resources.path(package, '__init__.py') as p:
            return str(p.parent.joinpath(path))
