callbacks = []

def subscribe(type, callback):
    callbacks.append((type, callback))
    
def notify(event):
    for type, callback in callbacks:
        if isinstance(event, type):
            callback(event)

class ProcessCommunicationEvent:
    # event mode tokens
    BEGIN_TOKEN = '<!--XSUPERVISOR:BEGIN-->'
    END_TOKEN   = '<!--XSUPERVISOR:END-->'
    def __init__(self, process_name, data):
        self.process_name = process_name
        self.data = data
