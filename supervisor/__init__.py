__import__('pkg_resources').declare_namespace(__name__)

def read_file(filename, mode='r'):
    f = open(filename, mode)
    content = f.read()
    f.close()
    return content

