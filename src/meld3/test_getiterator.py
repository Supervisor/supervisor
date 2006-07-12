#!/Users/chrism/projects/revelation/bin/python
import hotshot
import hotshot.stats
import meld3
# get rid of the noise of setting up an encoding
# in profile output
'.'.encode('utf-8')

template = """<html xmlns:meld="http://www.plope.com/software/meld3">
  <head>
    <title meld:id="title">This is the title</title>
    <div meld:id="headslot">This is the head slot</div>
  </head>
  <body>
   <div meld:id="content_well">
     <form meld:id="form1" action="." method="POST">
     <table border="0" meld:id="table1">
       <tbody meld:id="tbody">
         <tr meld:id="tr" class="foo">
           <td meld:id="td1">Name</td>
           <td meld:id="td2">Description</td>
         </tr>
       </tbody>
     </table>
     </form>
    </div>
  </body>
</html>"""

class IO:
    def __init__(self):
        self.data = ''

    def write(self, data):
        self.data += data

def run(root):
    clone = root.clone()
    print clone.getiterator()

if __name__ == '__main__':
    profiler= hotshot.Profile("logfile.dat")
    root = meld3.parse_xmlstring(template)
    profiler.run("run(root)")
    profiler.close() 
    stats = hotshot.stats.load("logfile.dat")
    stats.strip_dirs()
    #stats.sort_stats('cumulative', 'calls')
    stats.sort_stats('calls')
    stats.print_stats(200)

