xml = """<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml"
      xmlns:meld="http://www.plope.com/software/meld3"
      xmlns:bar="http://foo/bar">
  <head>
    <meta content="text/html; charset=ISO-8859-1" http-equiv="content-type" />
    <title meld:id="title">This is the title</title>
  </head>
  <body>
    <div/> <!-- empty tag -->
    <div meld:id="content_well">
      <form meld:id="form1" action="." method="POST">
      <table border="0" meld:id="table1">
        <tbody meld:id="tbody">
          <tr>
            <th>Name</th>
            <th>Description</th>
          </tr>
          <tr meld:id="tr" class="foo">
            <td meld:id="td1">Name</td>
            <td meld:id="td2">Description</td>
          </tr>
        </tbody>
      </table>
      <input type="submit" name="next" value=" Next "/>
      </form>
    </div>
  </body>
</html>
"""
from meld3 import parse_xmlstring
from meld3 import parse_htmlstring
from StringIO import StringIO
import sys

root = parse_xmlstring(xml)
root.findmeld('title').content('My document')
root.findmeld('form1').attributes(action='./handler')
data = (
    {'name':'Boys',
     'description':'Ugly'},
    {'name':'Girls',
     'description':'Pretty'},
    )
iterator = root.findmeld('tr').repeat(data)
for element, item in iterator:
    element.findmeld('td1').content(item['name'])
    element.findmeld('td2').content(item['description'])
root.write_xhtml(sys.stdout)


