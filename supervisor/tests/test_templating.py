# This file was originally based on the meld3 package version 2.0.0
# (https://pypi.org/project/meld3/2.0.0/).  The meld3 package is not
# called out separately in Supervisor's license or copyright files
# because meld3 had the same authors, copyright, and license as
# Supervisor at the time this file was bundled with Supervisor.

import unittest
import re
import sys

_SIMPLE_XML = r"""<?xml version="1.0"?>
<root xmlns:meld="https://github.com/Supervisor/supervisor">
  <list meld:id="list">
    <item meld:id="item">
       <name meld:id="name">Name</name>
       <description meld:id="description">Description</description>
    </item>
  </list>
</root>"""

_SIMPLE_XHTML = r"""<html xmlns="http://www.w3.org/1999/xhtml"
      xmlns:meld="https://github.com/Supervisor/supervisor">
   <body meld:id="body">Hello!</body>
</html>"""

_EMPTYTAGS_HTML = """<html>
  <body>
    <area/><base/><basefont/><br/><col/><frame/><hr/><img/><input/><isindex/>
    <link/><meta/><param/>
  </body>
</html>"""

_BOOLEANATTRS_XHTML= """<html>
  <body>
  <tag selected="true"/>
  <tag checked="true"/>
  <tag compact="true"/>
  <tag declare="true"/>
  <tag defer="true"/>
  <tag disabled="true"/>
  <tag ismap="true"/>
  <tag multiple="true"/>
  <tag nohref="true"/>
  <tag noresize="true"/>
  <tag noshade="true"/>
  <tag nowrap="true"/>
  </body>
</html>"""

_ENTITIES_XHTML= r"""
<html>
<head></head>
<body>
  <!-- test entity references -->
  <p>&nbsp;</p>
</body>
</html>"""

_COMPLEX_XHTML = r"""<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml"
      xmlns:meld="https://github.com/Supervisor/supervisor"
      xmlns:bar="http://foo/bar">
  <head>
    <meta content="text/html; charset=ISO-8859-1" http-equiv="content-type" />
    <title meld:id="title">This will be escaped in html output: &amp;</title>
    <script>this won't be escaped in html output: &amp;</script>
    <script type="text/javascript">
            //<![CDATA[
              // this won't be escaped in html output
              function match(a,b) {
                 if (a < b && a > 0) then { return 1 }
                }
             //]]>
    </script>
    <style>this won't be escaped in html output: &amp;</style>
  </head>
  <!-- a comment -->
  <body>
    <div bar:baz="slab"/>
    <div meld:id="content_well">
      <form meld:id="form1" action="." method="POST">
      <img src="foo.gif"/>
      <table border="0" meld:id="table1">
        <tbody meld:id="tbody">
          <tr meld:id="tr" class="foo">
            <td meld:id="td1">Name</td>
            <td meld:id="td2">Description</td>
          </tr>
        </tbody>
      </table>
      <input type="submit" name="submit" value=" Next "/>
      </form>
    </div>
  </body>
</html>"""

_NVU_HTML = """<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN">
<html>
<head>
  <meta content="text/html; charset=ISO-8859-1" http-equiv="content-type">
  <title meld:id="title">test doc</title>
</head>
<body>
 <!-- comment! -->
 Oh yeah...<br>
<br>
<table style="text-align: left; width: 100px;" border="1" cellpadding="2" cellspacing="2">
  <tbody>
    <tr>
      <td>Yup</td>
      <td>More </td>
      <td>Stuff</td>
      <td>Oh Yeah</td>
    </tr>
    <tr>
      <td>1</td>
      <td>2</td>
      <td>3</td>
      <td>4</td>
    </tr>
    <tr>
      <td></td>
      <td></td>
      <td></td>
      <td></td>
    </tr>
  </tbody>
</table>
<br>
<a href=".">And an image...</a><br>
<br>
<img style="width: 2048px; height: 1536px;" alt="dumb" src="IMG_0102.jpg">
</body>
</html>"""

_FILLMELDFORM_HTML = """\
<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.0 Transitional//EN">
<html>
<head>
 <title>Emergency Contacts</title>
</head>
<body>
   <div class="header">Emergency Contacts</div>

   <form action="." method="POST">
    <table>

      <tbody meld:id="tbody">

	<tr>
	  <th>Title</th>
	  <td>
	    <input type="text" name="honorific" size="6" value=""
		   meld:id="honorific"/>
	  </td>
	</tr>

	<tr>
	  <th>First Name</th>
	  <td>
	    <input type="text" name="firstname" size="20" value=""
		   meld:id="firstname"/>
	  </td>
	</tr>

	<tr>
	  <th>Middle Name</th>
	  <td>
	    <input type="text" name="middlename" size="15" value=""
		   meld:id="middlename"/>
	  </td>
	</tr>

	<tr>
	  <th>Last Name</th>
	  <td>
	    <input type="text" name="lastname" size="20" value=""
		   meld:id="lastname"/>
	  </td>
	</tr>

	<tr>

	  <th>Suffix</th>
	  <td style="width: 554px;">
          <select name="suffix" meld:id="suffix">
	      <option value="Jr.">Jr.</option>
	      <option value="Sr.">Sr.</option>
	      <option value="III">III</option>
	    </select>
          </td>

        </tr>

	<tr>
	  <th>Address 1</th>
	  <td>
	    <input type="text" name="address1" size="30" value=""
		   meld:id="address1"/>
	  </td>
	</tr>

	<tr>
	  <th>Address 2</th>
	  <td>
	    <input type="text" name="address2" size="30" value=""
		   meld:id="address2"/>
	  </td>
	</tr>

	<tr>
	  <th>City</th>
	  <td>
	    <input type="text" name="city" size="20" value=""
		   meld:id="city"/>
	  </td>
	</tr>

	<tr>
	  <th>State</th>
	  <td>
	    <input type="text" name="state" size="5" value=""
		   meld:id="state"/>
	  </td>
	</tr>

	<tr>
	  <th>ZIP</th>
	  <td>
	    <input type="text" name="zip" size="8" value=""
		   meld:id="zip"/>
	  </td>
	</tr>

	<tr>
	  <th>Home Phone</th>
	  <td>
	    <input type="text" name="homephone" size="12" value=""
		   meld:id="homephone"/>
	  </td>
	</tr>

	<tr>
	  <th>Cell/Mobile Phone</th>
	  <td>
	    <input type="text" name="cellphone" size="12" value=""
		   meld:id="cellphone"/>
	  </td>
	</tr>

	<tr>
	  <th>Email Address</th>
	  <td>
	    <input type="text" name="email" size="20" value=""
		   meld:id="email"/>
	  </td>
	</tr>

	<tr>
	  <th>Over 18? (Checkbox Boolean)</th>
	  <td>
            <input type="checkbox" name="over18" meld:id="over18"
                   value="true" checked="true"/>
	  </td>
	</tr>

	<tr>

	  <th>Mail OK? (Checkbox Ternary)</th>
          <td style="width: 554px;" meld:id="mailok:inputgroup">
            <input type="hidden" name="mailok:default"
                   value="false"/>
            <input type="checkbox" name="mailok"
                   value="true" checked/>
            <input type="checkbox" name="mailok"
                   value="false"/>
          </td>

        </tr>

	<tr>

	  <th>Favorite Color (Radio)</th>
          <td style="width: 554px;" meld:id="favorite_color:inputgroup">
            Red   <input type="radio" name="favorite_color"
                         value="Red"/>
            Green <input type="radio" name="favorite_color"
                         value="Green"/>
            Blue  <input type="radio" name="favorite_color"
                         value="Blue"/>
          </td>

        </tr>

	<tr>
	  <th></th>
	  <td>
	    <input type="submit" value=" Update " name="edit:method" />
	  </td>
	</tr>

      </tbody>
    </table>
    </form>

<p><a href="..">Return to list</a></p>
</body>
</html>
"""

class MeldAPITests(unittest.TestCase):
    def _makeElement(self, string):
        from supervisor.templating import parse_xmlstring
        return parse_xmlstring(string)

    def _makeElementFromHTML(self, string):
        from supervisor.templating import parse_htmlstring
        return parse_htmlstring(string)

    def test_findmeld(self):
        root = self._makeElement(_SIMPLE_XML)
        item = root.findmeld('item')
        self.assertEqual(item.tag, 'item')
        name = root.findmeld('name')
        self.assertEqual(name.text, 'Name')

    def test_findmeld_default(self):
        root = self._makeElement(_SIMPLE_XML)
        item = root.findmeld('item')
        self.assertEqual(item.tag, 'item')
        unknown = root.findmeld('unknown', 'foo')
        self.assertEqual(unknown, 'foo')
        self.assertEqual(root.findmeld('unknown'), None)

    def test_repeat_nochild(self):
        root = self._makeElement(_SIMPLE_XML)
        item = root.findmeld('item')
        self.assertEqual(item.tag, 'item')
        data = [{'name':'Jeff Buckley', 'description':'ethereal'},
                {'name':'Slipknot', 'description':'heavy'}]
        for element, d in item.repeat(data):
            element.findmeld('name').text = d['name']
            element.findmeld('description').text = d['description']
        self.assertEqual(item[0].text, 'Jeff Buckley')
        self.assertEqual(item[1].text, 'ethereal')

    def test_repeat_child(self):
        root = self._makeElement(_SIMPLE_XML)
        list = root.findmeld('list')
        self.assertEqual(list.tag, 'list')
        data = [{'name':'Jeff Buckley', 'description':'ethereal'},
                {'name':'Slipknot', 'description':'heavy'}]
        for element, d in list.repeat(data, 'item'):
            element.findmeld('name').text = d['name']
            element.findmeld('description').text = d['description']
        self.assertEqual(list[0][0].text, 'Jeff Buckley')
        self.assertEqual(list[0][1].text, 'ethereal')
        self.assertEqual(list[1][0].text, 'Slipknot')
        self.assertEqual(list[1][1].text, 'heavy')

    def test_mod(self):
        root = self._makeElement(_SIMPLE_XML)
        root % {'description':'foo', 'name':'bar'}
        name = root.findmeld('name')
        self.assertEqual(name.text, 'bar')
        desc = root.findmeld('description')
        self.assertEqual(desc.text, 'foo')

    def test_fillmelds(self):
        root = self._makeElement(_SIMPLE_XML)
        unfilled = root.fillmelds(**{'description':'foo', 'jammyjam':'a'})
        desc = root.findmeld('description')
        self.assertEqual(desc.text, 'foo')
        self.assertEqual(unfilled, ['jammyjam'])

    def test_fillmeldhtmlform(self):
        data = [
            {'honorific':'Mr.', 'firstname':'Chris', 'middlename':'Phillips',
             'lastname':'McDonough', 'address1':'802 Caroline St.',
             'address2':'Apt. 2B', 'city':'Fredericksburg', 'state': 'VA',
             'zip':'22401', 'homephone':'555-1212', 'cellphone':'555-1313',
             'email':'user@example.com', 'suffix':'Sr.', 'over18':True,
             'mailok:inputgroup':'true', 'favorite_color:inputgroup':'Green'},
            {'honorific':'Mr.', 'firstname':'Fred', 'middlename':'',
             'lastname':'Rogers', 'address1':'1 Imaginary Lane',
             'address2':'Apt. 3A', 'city':'Never Never Land', 'state': 'LA',
             'zip':'00001', 'homephone':'555-1111', 'cellphone':'555-4444',
             'email':'fred@neighborhood.com', 'suffix':'Jr.', 'over18':False,
             'mailok:inputgroup':'false','favorite_color:inputgroup':'Yellow',},
            {'firstname':'Fred', 'middlename':'',
             'lastname':'Rogers', 'address1':'1 Imaginary Lane',
             'address2':'Apt. 3A', 'city':'Never Never Land', 'state': 'LA',
             'zip':'00001', 'homephone':'555-1111', 'cellphone':'555-4444',
             'email':'fred@neighborhood.com', 'suffix':'IV', 'over18':False,
             'mailok:inputgroup':'false', 'favorite_color:inputgroup':'Blue',
             'notthere':1,},
            ]
        root = self._makeElementFromHTML(_FILLMELDFORM_HTML)

        clone = root.clone()
        unfilled = clone.fillmeldhtmlform(**data[0])
        self.assertEqual(unfilled, [])
        self.assertEqual(clone.findmeld('honorific').attrib['value'], 'Mr.')
        self.assertEqual(clone.findmeld('firstname').attrib['value'], 'Chris')
        middlename = clone.findmeld('middlename')
        self.assertEqual(middlename.attrib['value'], 'Phillips')
        suffix = clone.findmeld('suffix')
        self.assertEqual(suffix[1].attrib['selected'], 'selected')
        self.assertEqual(clone.findmeld('over18').attrib['checked'], 'checked')
        mailok = clone.findmeld('mailok:inputgroup')
        self.assertEqual(mailok[1].attrib['checked'], 'checked')
        favoritecolor = clone.findmeld('favorite_color:inputgroup')
        self.assertEqual(favoritecolor[1].attrib['checked'], 'checked')

        clone = root.clone()
        unfilled = clone.fillmeldhtmlform(**data[1])
        self.assertEqual(unfilled, ['favorite_color:inputgroup'])
        self.assertEqual(clone.findmeld('over18').attrib.get('checked'), None)
        mailok = clone.findmeld('mailok:inputgroup')
        self.assertEqual(mailok[2].attrib['checked'], 'checked')
        self.assertEqual(mailok[1].attrib.get('checked'), None)

        clone = root.clone()
        unfilled = clone.fillmeldhtmlform(**data[2])
        self.assertEqual(sorted(unfilled), ['notthere', 'suffix'])
        self.assertEqual(clone.findmeld('honorific').text, None)
        favoritecolor = clone.findmeld('favorite_color:inputgroup')
        self.assertEqual(favoritecolor[2].attrib['checked'], 'checked')
        self.assertEqual(favoritecolor[1].attrib.get('checked'), None)

    def test_replace_removes_all_elements(self):
        from supervisor.templating import Replace
        root = self._makeElement(_SIMPLE_XML)
        L = root.findmeld('list')
        L.replace('this is a textual replacement')
        R = root[0]
        self.assertEqual(R.tag, Replace)
        self.assertEqual(len(root.getchildren()), 1)

    def test_replace_replaces_the_right_element(self):
        from supervisor.templating import Replace
        root = self._makeElement(_SIMPLE_XML)
        D = root.findmeld('description')
        D.replace('this is a textual replacement')
        self.assertEqual(len(root.getchildren()), 1)
        L = root[0]
        self.assertEqual(L.tag, 'list')
        self.assertEqual(len(L.getchildren()), 1)
        I = L[0]
        self.assertEqual(I.tag, 'item')
        self.assertEqual(len(I.getchildren()), 2)
        N = I[0]
        self.assertEqual(N.tag, 'name')
        self.assertEqual(len(N.getchildren()), 0)
        D = I[1]
        self.assertEqual(D.tag, Replace)
        self.assertEqual(D.text, 'this is a textual replacement')
        self.assertEqual(len(D.getchildren()), 0)
        self.assertEqual(D.structure, False)

    def test_content(self):
        from supervisor.templating import Replace
        root = self._makeElement(_SIMPLE_XML)
        D = root.findmeld('description')
        D.content('this is a textual replacement')
        self.assertEqual(len(root.getchildren()), 1)
        L = root[0]
        self.assertEqual(L.tag, 'list')
        self.assertEqual(len(L.getchildren()), 1)
        I = L[0]
        self.assertEqual(I.tag, 'item')
        self.assertEqual(len(I.getchildren()), 2)
        N = I[0]
        self.assertEqual(N.tag, 'name')
        self.assertEqual(len(N.getchildren()), 0)
        D = I[1]
        self.assertEqual(D.tag, 'description')
        self.assertEqual(D.text, None)
        self.assertEqual(len(D.getchildren()), 1)
        T = D[0]
        self.assertEqual(T.tag, Replace)
        self.assertEqual(T.text, 'this is a textual replacement')
        self.assertEqual(T.structure, False)

    def test_attributes(self):
        from supervisor.templating import _MELD_ID
        root = self._makeElement(_COMPLEX_XHTML)
        D = root.findmeld('form1')
        D.attributes(foo='bar', baz='1', g='2', action='#')
        self.assertEqual(D.attrib, {
            'foo':'bar', 'baz':'1', 'g':'2',
            'method':'POST', 'action':'#',
            _MELD_ID: 'form1'})

    def test_attributes_unicode(self):
        from supervisor.templating import _MELD_ID
        from supervisor.compat import as_string
        root = self._makeElement(_COMPLEX_XHTML)
        D = root.findmeld('form1')
        D.attributes(foo=as_string('bar', encoding='latin1'),
                     action=as_string('#', encoding='latin1'))
        self.assertEqual(D.attrib, {
            'foo':as_string('bar', encoding='latin1'),
            'method':'POST', 'action': as_string('#', encoding='latin1'),
            _MELD_ID: 'form1'})

    def test_attributes_nonstringtype_raises(self):
        root = self._makeElement('<root></root>')
        self.assertRaises(ValueError, root.attributes, foo=1)

class MeldElementInterfaceTests(unittest.TestCase):
    def _getTargetClass(self):
        from supervisor.templating import _MeldElementInterface
        return _MeldElementInterface

    def _makeOne(self, *arg, **kw):
        klass = self._getTargetClass()
        return klass(*arg, **kw)

    def test_repeat(self):
        root = self._makeOne('root', {})
        from supervisor.templating import _MELD_ID
        item = self._makeOne('item', {_MELD_ID:'item'})
        record = self._makeOne('record', {_MELD_ID:'record'})
        name = self._makeOne('name', {_MELD_ID:'name'})
        description = self._makeOne('description', {_MELD_ID:'description'})
        record.append(name)
        record.append(description)
        item.append(record)
        root.append(item)

        data = [{'name':'Jeff Buckley', 'description':'ethereal'},
                {'name':'Slipknot', 'description':'heavy'}]

        for element, d in item.repeat(data):
            element.findmeld('name').text = d['name']
            element.findmeld('description').text = d['description']
        self.assertEqual(len(root), 2)
        item1 = root[0]
        self.assertEqual(len(item1), 1)

        record1 = item1[0]
        self.assertEqual(len(record1), 2)

        name1 = record1[0]
        desc1 = record1[1]
        self.assertEqual(name1.text, 'Jeff Buckley')
        self.assertEqual(desc1.text, 'ethereal')

        item2 = root[1]
        self.assertEqual(len(item2), 1)
        record2 = item2[0]
        self.assertEqual(len(record2), 2)
        name2 = record2[0]
        desc2 = record2[1]
        self.assertEqual(name2.text, 'Slipknot')
        self.assertEqual(desc2.text, 'heavy')

    def test_content_simple_nostructure(self):
        el = self._makeOne('div', {'id':'thediv'})
        el.content('hello')
        self.assertEqual(len(el._children), 1)
        replacenode = el._children[0]
        self.assertEqual(replacenode.parent, el)
        self.assertEqual(replacenode.text, 'hello')
        self.assertEqual(replacenode.structure, False)
        from supervisor.templating import Replace
        self.assertEqual(replacenode.tag, Replace)

    def test_content_simple_structure(self):
        el = self._makeOne('div', {'id':'thediv'})
        el.content('hello', structure=True)
        self.assertEqual(len(el._children), 1)
        replacenode = el._children[0]
        self.assertEqual(replacenode.parent, el)
        self.assertEqual(replacenode.text, 'hello')
        self.assertEqual(replacenode.structure, True)
        from supervisor.templating import Replace
        self.assertEqual(replacenode.tag, Replace)

    def test_findmeld_simple(self):
        from supervisor.templating import _MELD_ID
        el = self._makeOne('div', {_MELD_ID:'thediv'})
        self.assertEqual(el.findmeld('thediv'), el)

    def test_findmeld_simple_oneleveldown(self):
        from supervisor.templating import _MELD_ID
        el = self._makeOne('div', {_MELD_ID:'thediv'})
        span = self._makeOne('span', {_MELD_ID:'thespan'})
        el.append(span)
        self.assertEqual(el.findmeld('thespan'), span)

    def test_findmeld_simple_twolevelsdown(self):
        from supervisor.templating import _MELD_ID
        el = self._makeOne('div', {_MELD_ID:'thediv'})
        span = self._makeOne('span', {_MELD_ID:'thespan'})
        a = self._makeOne('a', {_MELD_ID:'thea'})
        span.append(a)
        el.append(span)
        self.assertEqual(el.findmeld('thea'), a)

    def test_ctor(self):
        iface = self._makeOne('div', {'id':'thediv'})
        self.assertEqual(iface.parent, None)
        self.assertEqual(iface.tag, 'div')
        self.assertEqual(iface.attrib, {'id':'thediv'})

    def test_getiterator_simple(self):
        div = self._makeOne('div', {'id':'thediv'})
        iterator = div.getiterator()
        self.assertEqual(len(iterator), 1)
        self.assertEqual(iterator[0], div)

    def test_getiterator(self):
        div = self._makeOne('div', {'id':'thediv'})
        span = self._makeOne('span', {})
        span2 = self._makeOne('span', {'id':'2'})
        span3 = self._makeOne('span3', {'id':'3'})
        span3.text = 'abc'
        span3.tail = '  '
        div.append(span)
        span.append(span2)
        span2.append(span3)

        it = div.getiterator()
        self.assertEqual(len(it), 4)
        self.assertEqual(it[0], div)
        self.assertEqual(it[1], span)
        self.assertEqual(it[2], span2)
        self.assertEqual(it[3], span3)

    def test_getiterator_tag_ignored(self):
        div = self._makeOne('div', {'id':'thediv'})
        span = self._makeOne('span', {})
        span2 = self._makeOne('span', {'id':'2'})
        span3 = self._makeOne('span3', {'id':'3'})
        span3.text = 'abc'
        span3.tail = '  '
        div.append(span)
        span.append(span2)
        span2.append(span3)

        it = div.getiterator(tag='div')
        self.assertEqual(len(it), 4)
        self.assertEqual(it[0], div)
        self.assertEqual(it[1], span)
        self.assertEqual(it[2], span2)
        self.assertEqual(it[3], span3)

    def test_append(self):
        div = self._makeOne('div', {'id':'thediv'})
        span = self._makeOne('span', {})
        div.append(span)
        self.assertEqual(div[0].tag, 'span')
        self.assertEqual(span.parent, div)

    def test__setitem__(self):
        div = self._makeOne('div', {'id':'thediv'})
        span = self._makeOne('span', {})
        span2 = self._makeOne('span', {'id':'2'})
        div.append(span)
        div[0] = span2
        self.assertEqual(div[0].tag, 'span')
        self.assertEqual(div[0].attrib, {'id':'2'})
        self.assertEqual(div[0].parent, div)

    def test_insert(self):
        div = self._makeOne('div', {'id':'thediv'})
        span = self._makeOne('span', {})
        span2 = self._makeOne('span', {'id':'2'})
        div.append(span)
        div.insert(0, span2)
        self.assertEqual(div[0].tag, 'span')
        self.assertEqual(div[0].attrib, {'id':'2'})
        self.assertEqual(div[0].parent, div)
        self.assertEqual(div[1].tag, 'span')
        self.assertEqual(div[1].attrib, {})
        self.assertEqual(div[1].parent, div)

    def test_clone_simple(self):
        div = self._makeOne('div', {'id':'thediv'})
        div.text = 'abc'
        div.tail = '   '
        span = self._makeOne('span', {})
        div.append(span)
        div.clone()

    def test_clone(self):
        div = self._makeOne('div', {'id':'thediv'})
        span = self._makeOne('span', {})
        span2 = self._makeOne('span', {'id':'2'})
        span3 = self._makeOne('span3', {'id':'3'})
        span3.text = 'abc'
        span3.tail = '  '
        div.append(span)
        span.append(span2)
        span2.append(span3)

        div2 = div.clone()
        self.assertEqual(div.tag, div2.tag)
        self.assertEqual(div.attrib, div2.attrib)
        self.assertEqual(div[0].tag, div2[0].tag)
        self.assertEqual(div[0].attrib, div2[0].attrib)
        self.assertEqual(div[0][0].tag, div2[0][0].tag)
        self.assertEqual(div[0][0].attrib, div2[0][0].attrib)
        self.assertEqual(div[0][0][0].tag, div2[0][0][0].tag)
        self.assertEqual(div[0][0][0].attrib, div2[0][0][0].attrib)
        self.assertEqual(div[0][0][0].text, div2[0][0][0].text)
        self.assertEqual(div[0][0][0].tail, div2[0][0][0].tail)

        self.assertNotEqual(id(div), id(div2))
        self.assertNotEqual(id(div[0]), id(div2[0]))
        self.assertNotEqual(id(div[0][0]), id(div2[0][0]))
        self.assertNotEqual(id(div[0][0][0]), id(div2[0][0][0]))

    def test_deparent_noparent(self):
        div = self._makeOne('div', {})
        self.assertEqual(div.parent, None)
        div.deparent()
        self.assertEqual(div.parent, None)

    def test_deparent_withparent(self):
        parent = self._makeOne('parent', {})
        self.assertEqual(parent.parent, None)
        child = self._makeOne('child', {})
        parent.append(child)
        self.assertEqual(parent.parent, None)
        self.assertEqual(child.parent, parent)
        self.assertEqual(parent[0], child)
        child.deparent()
        self.assertEqual(child.parent, None)
        self.assertRaises(IndexError, parent.__getitem__, 0)

    def test_setslice(self):
        parent = self._makeOne('parent', {})
        child1 = self._makeOne('child1', {})
        child2 = self._makeOne('child2', {})
        child3 = self._makeOne('child3', {})
        children = (child1, child2, child3)
        parent[0:2] = children
        self.assertEqual(child1.parent, parent)
        self.assertEqual(child2.parent, parent)
        self.assertEqual(child3.parent, parent)
        self.assertEqual(parent._children, list(children))

    def test_delslice(self):
        parent = self._makeOne('parent', {})
        child1 = self._makeOne('child1', {})
        child2 = self._makeOne('child2', {})
        child3 = self._makeOne('child3', {})
        children = (child1, child2, child3)
        parent[0:2] = children
        del parent[0:2]
        self.assertEqual(child1.parent, None)
        self.assertEqual(child2.parent, None)
        self.assertEqual(child3.parent, parent)
        self.assertEqual(len(parent._children), 1)

    def test_remove(self):
        parent = self._makeOne('parent', {})
        child1 = self._makeOne('child1', {})
        parent.append(child1)
        parent.remove(child1)
        self.assertEqual(child1.parent, None)
        self.assertEqual(len(parent._children), 0)

    def test_lineage(self):
        from supervisor.templating import _MELD_ID
        div1 = self._makeOne('div', {_MELD_ID:'div1'})
        span1 = self._makeOne('span', {_MELD_ID:'span1'})
        span2 = self._makeOne('span', {_MELD_ID:'span2'})
        span3 = self._makeOne('span', {_MELD_ID:'span3'})
        span4 = self._makeOne('span', {_MELD_ID:'span4'})
        span5 = self._makeOne('span', {_MELD_ID:'span5'})
        span6 = self._makeOne('span', {_MELD_ID:'span6'})
        unknown = self._makeOne('span', {})
        div2 = self._makeOne('div2', {_MELD_ID:'div2'})
        div1.append(span1)
        span1.append(span2)
        span2.append(span3)
        span3.append(unknown)
        unknown.append(span4)
        span4.append(span5)
        span5.append(span6)
        div1.append(div2)
        def ids(L):
            return [ x.meldid() for x in L ]
        self.assertEqual(ids(div1.lineage()), ['div1'])
        self.assertEqual(ids(span1.lineage()), ['span1', 'div1'])
        self.assertEqual(ids(span2.lineage()), ['span2', 'span1', 'div1'])
        self.assertEqual(ids(span3.lineage()), ['span3', 'span2', 'span1',
                                                    'div1'])
        self.assertEqual(ids(unknown.lineage()), [None, 'span3', 'span2',
                                                  'span1',
                                                  'div1'])
        self.assertEqual(ids(span4.lineage()), ['span4', None, 'span3',
                                                'span2',
                                                'span1','div1'])

        self.assertEqual(ids(span5.lineage()), ['span5', 'span4', None,
                                                'span3', 'span2',
                                                'span1','div1'])
        self.assertEqual(ids(span6.lineage()), ['span6', 'span5', 'span4',
                                                None,'span3', 'span2',
                                                    'span1','div1'])
        self.assertEqual(ids(div2.lineage()), ['div2', 'div1'])


    def test_shortrepr(self):
        from supervisor.compat import as_bytes
        div = self._makeOne('div', {'id':'div1'})
        span = self._makeOne('span', {})
        span2 = self._makeOne('span', {'id':'2'})
        div2 = self._makeOne('div2', {'id':'div2'})
        div.append(span)
        span.append(span2)
        div.append(div2)
        r = div.shortrepr()
        self.assertEqual(r,
            as_bytes('<div id="div1"><span><span id="2"></span></span>'
                     '<div2 id="div2"></div2></div>', encoding='latin1'))

    def test_shortrepr2(self):
        from supervisor.templating import parse_xmlstring
        from supervisor.compat import as_bytes
        root = parse_xmlstring(_COMPLEX_XHTML)
        r = root.shortrepr()
        self.assertEqual(r,
            as_bytes('<html>\n'
               '  <head>\n'
               '    <meta content="text/html; charset=ISO-8859-1" '
                         'http-equiv="content-type">\n'
               '     [...]\n</head>\n'
               '  <!--  a comment  -->\n'
               '   [...]\n'
               '</html>', encoding='latin1'))

    def test_diffmeld1(self):
        from supervisor.templating import parse_xmlstring
        from supervisor.templating import _MELD_ID
        root = parse_xmlstring(_COMPLEX_XHTML)
        clone = root.clone()
        div = self._makeOne('div', {_MELD_ID:'newdiv'})
        clone.append(div)
        tr = clone.findmeld('tr')
        tr.deparent()
        title = clone.findmeld('title')
        title.deparent()
        clone.append(title)

        # unreduced
        diff = root.diffmeld(clone)
        changes = diff['unreduced']
        addedtags = [ x.attrib[_MELD_ID] for x in changes['added'] ]
        removedtags = [x.attrib[_MELD_ID] for x in changes['removed'] ]
        movedtags = [ x.attrib[_MELD_ID] for x in changes['moved'] ]
        addedtags.sort()
        removedtags.sort()
        movedtags.sort()
        self.assertEqual(addedtags,['newdiv'])
        self.assertEqual(removedtags,['td1', 'td2', 'tr'])
        self.assertEqual(movedtags, ['title'])

        # reduced
        changes = diff['reduced']
        addedtags = [ x.attrib[_MELD_ID] for x in changes['added'] ]
        removedtags = [x.attrib[_MELD_ID] for x in changes['removed'] ]
        movedtags = [ x.attrib[_MELD_ID] for x in changes['moved'] ]
        addedtags.sort()
        removedtags.sort()
        movedtags.sort()
        self.assertEqual(addedtags,['newdiv'])
        self.assertEqual(removedtags,['tr'])
        self.assertEqual(movedtags, ['title'])

    def test_diffmeld2(self):
        source = """
        <root>
          <a meld:id="a">
             <b meld:id="b"></b>
          </a>
        </root>"""
        target = """
        <root>
          <a meld:id="a"></a>
          <b meld:id="b"></b>
        </root>
        """
        from supervisor.templating import parse_htmlstring
        source_root = parse_htmlstring(source)
        target_root = parse_htmlstring(target)
        changes = source_root.diffmeld(target_root)

        # unreduced
        actual = [x.meldid() for x in changes['unreduced']['moved']]
        expected = ['b']
        self.assertEqual(expected, actual)

        actual = [x.meldid() for x in changes['unreduced']['added']]
        expected = []
        self.assertEqual(expected, actual)

        actual = [x.meldid() for x in changes['unreduced']['removed']]
        expected = []
        self.assertEqual(expected, actual)

        # reduced
        actual = [x.meldid() for x in changes['reduced']['moved']]
        expected = ['b']
        self.assertEqual(expected, actual)

        actual = [x.meldid() for x in changes['reduced']['added']]
        expected = []
        self.assertEqual(expected, actual)

        actual = [x.meldid() for x in changes['reduced']['removed']]
        expected = []
        self.assertEqual(expected, actual)


    def test_diffmeld3(self):
        source = """
        <root>
          <a meld:id="a">
             <b meld:id="b">
               <c meld:id="c"></c>
             </b>
          </a>
          <z meld:id="z">
            <y meld:id="y"></y>
          </z>
        </root>
        """
        target = """
        <root>
          <b meld:id="b">
            <c meld:id="c"></c>
          </b>
          <a meld:id="a"></a>
          <d meld:id="d">
             <e meld:id="e"></e>
          </d>
        </root>
        """
        from supervisor.templating import parse_htmlstring
        source_root = parse_htmlstring(source)
        target_root = parse_htmlstring(target)
        changes = source_root.diffmeld(target_root)

        # unreduced
        actual = [x.meldid() for x in changes['unreduced']['moved']]
        expected = ['b', 'c']
        self.assertEqual(expected, actual)

        actual = [x.meldid() for x in changes['unreduced']['added']]
        expected = ['d', 'e']
        self.assertEqual(expected, actual)

        actual = [x.meldid() for x in changes['unreduced']['removed']]
        expected = ['z', 'y']
        self.assertEqual(expected, actual)

        # reduced
        actual = [x.meldid() for x in changes['reduced']['moved']]
        expected = ['b']
        self.assertEqual(expected, actual)

        actual = [x.meldid() for x in changes['reduced']['added']]
        expected = ['d']
        self.assertEqual(expected, actual)

        actual = [x.meldid() for x in changes['reduced']['removed']]
        expected = ['z']
        self.assertEqual(expected, actual)

    def test_diffmeld4(self):
        source = """
        <root>
          <a meld:id="a">
             <b meld:id="b">
               <c meld:id="c">
                 <d meld:id="d"></d>
               </c>
             </b>
          </a>
          <z meld:id="z">
            <y meld:id="y"></y>
          </z>
        </root>
        """
        target = """
        <root>
          <p>
            <a meld:id="a">
               <b meld:id="b"></b>
            </a>
          </p>
          <p>
            <m meld:id="m">
              <n meld:id="n"></n>
            </m>
          </p>
        </root>
        """
        from supervisor.templating import parse_htmlstring
        source_root = parse_htmlstring(source)
        target_root = parse_htmlstring(target)
        changes = source_root.diffmeld(target_root)

        # unreduced
        actual = [x.meldid() for x in changes['unreduced']['moved']]
        expected = ['a', 'b']
        self.assertEqual(expected, actual)

        actual = [x.meldid() for x in changes['unreduced']['added']]
        expected = ['m', 'n']
        self.assertEqual(expected, actual)

        actual = [x.meldid() for x in changes['unreduced']['removed']]
        expected = ['c', 'd', 'z', 'y']
        self.assertEqual(expected, actual)

        # reduced
        actual = [x.meldid() for x in changes['reduced']['moved']]
        expected = ['a']
        self.assertEqual(expected, actual)

        actual = [x.meldid() for x in changes['reduced']['added']]
        expected = ['m']
        self.assertEqual(expected, actual)

        actual = [x.meldid() for x in changes['reduced']['removed']]
        expected = ['c', 'z']
        self.assertEqual(expected, actual)

    def test_diffmeld5(self):
        source = """
        <root>
          <a meld:id="a">
             <b meld:id="b">
               <c meld:id="c">
                 <d meld:id="d"></d>
               </c>
             </b>
          </a>
          <z meld:id="z">
            <y meld:id="y"></y>
          </z>
        </root>
        """
        target = """
        <root>
          <p>
            <a meld:id="a">
               <b meld:id="b">
                 <p>
                   <c meld:id="c">
                     <d meld:id="d"></d>
                   </c>
                 </p>
               </b>
            </a>
          </p>
          <z meld:id="z">
            <y meld:id="y"></y>
          </z>
        </root>
        """
        from supervisor.templating import parse_htmlstring
        source_root = parse_htmlstring(source)
        target_root = parse_htmlstring(target)
        changes = source_root.diffmeld(target_root)

        # unreduced
        actual = [x.meldid() for x in changes['unreduced']['moved']]
        expected = ['a', 'b', 'c', 'd']
        self.assertEqual(expected, actual)

        actual = [x.meldid() for x in changes['unreduced']['added']]
        expected = []
        self.assertEqual(expected, actual)

        actual = [x.meldid() for x in changes['unreduced']['removed']]
        expected = []
        self.assertEqual(expected, actual)

        # reduced
        actual = [x.meldid() for x in changes['reduced']['moved']]
        expected = ['a', 'c']
        self.assertEqual(expected, actual)

        actual = [x.meldid() for x in changes['reduced']['added']]
        expected = []
        self.assertEqual(expected, actual)

        actual = [x.meldid() for x in changes['reduced']['removed']]
        expected = []
        self.assertEqual(expected, actual)



class ParserTests(unittest.TestCase):
    def _parse(self, *args):
        from supervisor.templating import parse_xmlstring
        root = parse_xmlstring(*args)
        return root

    def _parse_html(self, *args):
        from supervisor.templating import parse_htmlstring
        root = parse_htmlstring(*args)
        return root

    def test_parse_simple_xml(self):
        from supervisor.templating import _MELD_ID
        root = self._parse(_SIMPLE_XML)
        self.assertEqual(root.tag, 'root')
        self.assertEqual(root.parent, None)
        l1st = root[0]
        self.assertEqual(l1st.tag, 'list')
        self.assertEqual(l1st.parent, root)
        self.assertEqual(l1st.attrib[_MELD_ID], 'list')
        item = l1st[0]
        self.assertEqual(item.tag, 'item')
        self.assertEqual(item.parent, l1st)
        self.assertEqual(item.attrib[_MELD_ID], 'item')
        name = item[0]
        description = item[1]
        self.assertEqual(name.tag, 'name')
        self.assertEqual(name.parent, item)
        self.assertEqual(name.attrib[_MELD_ID], 'name')
        self.assertEqual(description.tag, 'description')
        self.assertEqual(description.parent, item)
        self.assertEqual(description.attrib[_MELD_ID], 'description')

    def test_parse_simple_xhtml(self):
        xhtml_ns = '{http://www.w3.org/1999/xhtml}%s'
        from supervisor.templating import _MELD_ID

        root = self._parse(_SIMPLE_XHTML)
        self.assertEqual(root.tag, xhtml_ns % 'html')
        self.assertEqual(root.attrib, {})
        self.assertEqual(root.parent, None)
        body = root[0]
        self.assertEqual(body.tag, xhtml_ns % 'body')
        self.assertEqual(body.attrib[_MELD_ID], 'body')
        self.assertEqual(body.parent, root)

    def test_parse_complex_xhtml(self):
        xhtml_ns = '{http://www.w3.org/1999/xhtml}%s'
        from supervisor.templating import _MELD_ID
        root = self._parse(_COMPLEX_XHTML)
        self.assertEqual(root.tag, xhtml_ns % 'html')
        self.assertEqual(root.attrib, {})
        self.assertEqual(root.parent, None)
        head = root[0]
        self.assertEqual(head.tag, xhtml_ns % 'head')
        self.assertEqual(head.attrib, {})
        self.assertEqual(head.parent, root)
        meta = head[0]
        self.assertEqual(meta.tag, xhtml_ns % 'meta')
        self.assertEqual(meta.attrib['content'],
                         'text/html; charset=ISO-8859-1')
        self.assertEqual(meta.parent, head)
        title = head[1]
        self.assertEqual(title.tag, xhtml_ns % 'title')
        self.assertEqual(title.attrib[_MELD_ID], 'title')
        self.assertEqual(title.parent, head)

        body = root[2]
        self.assertEqual(body.tag, xhtml_ns % 'body')
        self.assertEqual(body.attrib, {})
        self.assertEqual(body.parent, root)

        div1 = body[0]
        self.assertEqual(div1.tag, xhtml_ns % 'div')
        self.assertEqual(div1.attrib, {'{http://foo/bar}baz': 'slab'})
        self.assertEqual(div1.parent, body)

        div2 = body[1]
        self.assertEqual(div2.tag, xhtml_ns % 'div')
        self.assertEqual(div2.attrib[_MELD_ID], 'content_well')
        self.assertEqual(div2.parent, body)

        form = div2[0]
        self.assertEqual(form.tag, xhtml_ns % 'form')
        self.assertEqual(form.attrib[_MELD_ID], 'form1')
        self.assertEqual(form.attrib['action'], '.')
        self.assertEqual(form.attrib['method'], 'POST')
        self.assertEqual(form.parent, div2)

        img = form[0]
        self.assertEqual(img.tag, xhtml_ns % 'img')
        self.assertEqual(img.parent, form)

        table = form[1]
        self.assertEqual(table.tag, xhtml_ns % 'table')
        self.assertEqual(table.attrib[_MELD_ID], 'table1')
        self.assertEqual(table.attrib['border'], '0')
        self.assertEqual(table.parent, form)

        tbody = table[0]
        self.assertEqual(tbody.tag, xhtml_ns % 'tbody')
        self.assertEqual(tbody.attrib[_MELD_ID], 'tbody')
        self.assertEqual(tbody.parent, table)

        tr = tbody[0]
        self.assertEqual(tr.tag, xhtml_ns % 'tr')
        self.assertEqual(tr.attrib[_MELD_ID], 'tr')
        self.assertEqual(tr.attrib['class'], 'foo')
        self.assertEqual(tr.parent, tbody)

        td1 = tr[0]
        self.assertEqual(td1.tag, xhtml_ns % 'td')
        self.assertEqual(td1.attrib[_MELD_ID], 'td1')
        self.assertEqual(td1.parent, tr)

        td2 = tr[1]
        self.assertEqual(td2.tag, xhtml_ns % 'td')
        self.assertEqual(td2.attrib[_MELD_ID], 'td2')
        self.assertEqual(td2.parent, tr)

    def test_nvu_html(self):
        from supervisor.templating import _MELD_ID
        from supervisor.templating import Comment
        root = self._parse_html(_NVU_HTML)
        self.assertEqual(root.tag, 'html')
        self.assertEqual(root.attrib, {})
        self.assertEqual(root.parent, None)
        head = root[0]
        self.assertEqual(head.tag, 'head')
        self.assertEqual(head.attrib, {})
        self.assertEqual(head.parent, root)
        meta = head[0]
        self.assertEqual(meta.tag, 'meta')
        self.assertEqual(meta.attrib['content'],
                         'text/html; charset=ISO-8859-1')
        title = head[1]
        self.assertEqual(title.tag, 'title')
        self.assertEqual(title.attrib[_MELD_ID], 'title')
        self.assertEqual(title.parent, head)

        body = root[1]
        self.assertEqual(body.tag, 'body')
        self.assertEqual(body.attrib, {})
        self.assertEqual(body.parent, root)

        comment = body[0]
        self.assertEqual(comment.tag, Comment)

        table = body[3]
        self.assertEqual(table.tag, 'table')
        self.assertEqual(table.attrib, {'style':
                                        'text-align: left; width: 100px;',
                                        'border':'1',
                                        'cellpadding':'2',
                                        'cellspacing':'2'})
        self.assertEqual(table.parent, body)
        href = body[5]
        self.assertEqual(href.tag, 'a')
        img = body[8]
        self.assertEqual(img.tag, 'img')


    def test_dupe_meldids_fails_parse_xml(self):
        meld_ns = "https://github.com/Supervisor/supervisor"
        repeated = ('<html xmlns:meld="%s" meld:id="repeat">'
                    '<body meld:id="repeat"/></html>' % meld_ns)
        self.assertRaises(ValueError, self._parse, repeated)

    def test_dupe_meldids_fails_parse_html(self):
        meld_ns = "https://github.com/Supervisor/supervisor"
        repeated = ('<html xmlns:meld="%s" meld:id="repeat">'
                    '<body meld:id="repeat"/></html>' % meld_ns)
        self.assertRaises(ValueError, self._parse_html, repeated)

class UtilTests(unittest.TestCase):

    def test_insert_xhtml_doctype(self):
        from supervisor.templating import insert_doctype
        orig = '<root></root>'
        actual = insert_doctype(orig)
        expected = '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd"><root></root>'
        self.assertEqual(actual, expected)

    def test_insert_doctype_after_xmldecl(self):
        from supervisor.templating import insert_doctype
        orig = '<?xml version="1.0" encoding="latin-1"?><root></root>'
        actual = insert_doctype(orig)
        expected = '<?xml version="1.0" encoding="latin-1"?><!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd"><root></root>'
        self.assertEqual(actual, expected)

    def test_insert_meld_ns_decl(self):
        from supervisor.templating import insert_meld_ns_decl
        orig = '<?xml version="1.0" encoding="latin-1"?><root></root>'
        actual = insert_meld_ns_decl(orig)
        expected = '<?xml version="1.0" encoding="latin-1"?><root xmlns:meld="https://github.com/Supervisor/supervisor"></root>'
        self.assertEqual(actual, expected)

    def test_prefeed_preserves_existing_meld_ns(self):
        from supervisor.templating import prefeed
        orig = '<?xml version="1.0" encoding="latin-1"?><root xmlns:meld="#"></root>'
        actual = prefeed(orig)
        expected = '<?xml version="1.0" encoding="latin-1"?><!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd"><root xmlns:meld="#"></root>'
        self.assertEqual(actual, expected)

    def test_prefeed_preserves_existing_doctype(self):
        from supervisor.templating import prefeed
        orig = '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd"><root xmlns:meld="https://github.com/Supervisor/supervisor"></root>'
        actual = prefeed(orig)
        self.assertEqual(actual, orig)

class WriterTests(unittest.TestCase):
    def _parse(self, xml):
        from supervisor.templating import parse_xmlstring
        root = parse_xmlstring(xml)
        return root

    def _parse_html(self, xml):
        from supervisor.templating import parse_htmlstring
        root = parse_htmlstring(xml)
        return root

    def _write(self, fn, **kw):
        try:
            from io import BytesIO
        except: # python 2.5
            from StringIO import StringIO as BytesIO
        out = BytesIO()
        fn(out, **kw)
        out.seek(0)
        actual = out.read()
        return actual

    def _write_xml(self, node, **kw):
        return self._write(node.write_xml, **kw)

    def _write_html(self, node, **kw):
        return self._write(node.write_html, **kw)

    def _write_xhtml(self, node, **kw):
        return self._write(node.write_xhtml, **kw)

    def assertNormalizedXMLEqual(self, a, b):
        from supervisor.compat import as_string
        a = normalize_xml(as_string(a, encoding='latin1'))
        b = normalize_xml(as_string(b, encoding='latin1'))
        self.assertEqual(a, b)

    def assertNormalizedHTMLEqual(self, a, b):
        from supervisor.compat import as_string
        a = normalize_xml(as_string(a, encoding='latin1'))
        b = normalize_xml(as_string(b, encoding='latin1'))
        self.assertEqual(a, b)

    def test_write_simple_xml(self):
        root = self._parse(_SIMPLE_XML)
        actual = self._write_xml(root)
        expected = """<?xml version="1.0"?><root>
  <list>
    <item>
       <name>Name</name>
       <description>Description</description>
    </item>
  </list>
</root>"""
        self.assertNormalizedXMLEqual(actual, expected)

        for el, data in root.findmeld('item').repeat(((1,2),)):
            el.findmeld('name').text = str(data[0])
            el.findmeld('description').text = str(data[1])
        actual = self._write_xml(root)
        expected = """<?xml version="1.0"?><root>
  <list>
    <item>
       <name>1</name>
       <description>2</description>
    </item>
  </list>
</root>"""
        self.assertNormalizedXMLEqual(actual, expected)

    def test_write_simple_xhtml(self):
        root = self._parse(_SIMPLE_XHTML)
        actual = self._write_xhtml(root)
        expected = """<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd"><html><body>Hello!</body></html>"""
        self.assertNormalizedXMLEqual(actual, expected)

    def test_write_simple_xhtml_as_html(self):
        root = self._parse(_SIMPLE_XHTML)
        actual = self._write_html(root)
        expected = """<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN" "http://www.w3.org/TR/html4/loose.dtd">
<html>
   <body>Hello!</body>
</html>"""
        self.assertNormalizedHTMLEqual(actual, expected)

    def test_write_complex_xhtml_as_html(self):
        root = self._parse(_COMPLEX_XHTML)
        actual = self._write_html(root)
        expected = """<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN" "http://www.w3.org/TR/html4/loose.dtd">
<html>
  <head>
    <meta content="text/html; charset=ISO-8859-1" http-equiv="content-type">
    <title>This will be escaped in html output: &amp;</title>
    <script>this won't be escaped in html output: &</script>
    <script type="text/javascript">
            //
              // this won't be escaped in html output
              function match(a,b) {
                 if (a < b && a > 0) then { return 1 }
                }
             //
    </script>
    <style>this won't be escaped in html output: &</style>
  </head>
  <!-- a comment -->
  <body>
    <div></div>
    <div>
      <form action="." method="POST">
      <img src="foo.gif">
      <table border="0">
        <tbody>
          <tr class="foo">
            <td>Name</td>
            <td>Description</td>
          </tr>
        </tbody>
      </table>
      <input name="submit" type="submit" value=" Next ">
      </form>
    </div>
  </body>
</html>"""

        self.assertNormalizedHTMLEqual(actual, expected)

    def test_write_complex_xhtml_as_xhtml(self):
        # I'm not entirely sure if the cdata "script" quoting in this
        # test is entirely correct for XHTML.  Ryan Tomayko suggests
        # that escaped entities are handled properly in script tags by
        # XML-aware browsers at
        # http://sourceforge.net/mailarchive/message.php?msg_id=10835582
        # but I haven't tested it at all.  ZPT does not seem to do
        # this; it outputs unescaped data.
        root = self._parse(_COMPLEX_XHTML)
        actual = self._write_xhtml(root)
        expected = """<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html>
  <head>
    <meta content="text/html; charset=ISO-8859-1" http-equiv="content-type" />
    <title>This will be escaped in html output: &amp;</title>
    <script>this won't be escaped in html output: &amp;</script>
    <script type="text/javascript">
            //
              // this won't be escaped in html output
              function match(a,b) {
                 if (a &lt; b &amp;&amp; a > 0) then { return 1 }
                }
             //
    </script>
    <style>this won't be escaped in html output: &amp;</style>
  </head>
  <!--  a comment  -->
  <body>
    <div ns0:baz="slab" xmlns:ns0="http://foo/bar" />
    <div>
      <form action="." method="POST">
      <img src="foo.gif" />
      <table border="0">
        <tbody>
          <tr class="foo">
            <td>Name</td>
            <td>Description</td>
          </tr>
        </tbody>
      </table>
      <input name="submit" type="submit" value=" Next " />
      </form>
    </div>
  </body>
</html>"""
        self.assertNormalizedXMLEqual(actual, expected)

    def test_write_emptytags_html(self):
        from supervisor.compat import as_string
        root = self._parse(_EMPTYTAGS_HTML)
        actual = self._write_html(root)
        expected = """<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN" "http://www.w3.org/TR/html4/loose.dtd">
<html>
  <body>
    <area><base><basefont><br><col><frame><hr><img><input><isindex>
    <link><meta><param>
  </body>
</html>"""
        self.assertEqual(as_string(actual, encoding='latin1'), expected)

    def test_write_booleanattrs_xhtml_as_html(self):
        root = self._parse(_BOOLEANATTRS_XHTML)
        actual = self._write_html(root)
        expected = """<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN" "http://www.w3.org/TR/html4/loose.dtd">
<html>
  <body>
  <tag selected></tag>
  <tag checked></tag>
  <tag compact></tag>
  <tag declare></tag>
  <tag defer></tag>
  <tag disabled></tag>
  <tag ismap></tag>
  <tag multiple></tag>
  <tag nohref></tag>
  <tag noresize></tag>
  <tag noshade></tag>
  <tag nowrap></tag>
  </body>
</html>"""
        self.assertNormalizedHTMLEqual(actual, expected)

    def test_write_simple_xhtml_pipeline(self):
        root = self._parse(_SIMPLE_XHTML)
        actual = self._write_xhtml(root, pipeline=True)
        expected = """<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd"><html><body ns0:id="body" xmlns:ns0="https://github.com/Supervisor/supervisor">Hello!</body></html>"""
        self.assertNormalizedXMLEqual(actual, expected)

    def test_write_simple_xml_pipeline(self):
        root = self._parse(_SIMPLE_XML)
        actual = self._write_xml(root, pipeline=True)
        expected = """<?xml version="1.0"?><root>
  <list ns0:id="list" xmlns:ns0="https://github.com/Supervisor/supervisor">
    <item ns0:id="item">
       <name ns0:id="name">Name</name>
       <description ns0:id="description">Description</description>
    </item>
  </list>
</root>"""
        self.assertNormalizedXMLEqual(actual, expected)

    def test_write_simple_xml_override_encoding(self):
        root = self._parse(_SIMPLE_XML)
        actual = self._write_xml(root, encoding="latin-1")
        expected = """<?xml version="1.0" encoding="latin-1"?><root>
  <list>
    <item>
       <name>Name</name>
       <description>Description</description>
    </item>
  </list>
</root>"""
        self.assertNormalizedXMLEqual(actual, expected)


    def test_write_simple_xml_as_fragment(self):
        root = self._parse(_SIMPLE_XML)
        actual = self._write_xml(root, fragment=True)
        expected = """<root>
  <list>
    <item>
       <name>Name</name>
       <description>Description</description>
    </item>
  </list>
</root>"""
        self.assertNormalizedXMLEqual(actual, expected)

    def test_write_simple_xml_with_doctype(self):
        root = self._parse(_SIMPLE_XML)
        from supervisor.templating import doctype
        actual = self._write_xml(root, doctype=doctype.xhtml)
        expected = """<?xml version="1.0"?>
        <!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd"><root>
  <list>
    <item>
       <name>Name</name>
       <description>Description</description>
    </item>
  </list>
</root>"""
        self.assertNormalizedXMLEqual(actual, expected)

    def test_write_simple_xml_doctype_nodeclaration(self):
        root = self._parse(_SIMPLE_XML)
        from supervisor.templating import doctype
        actual = self._write_xml(root, declaration=False,
                                 doctype=doctype.xhtml)
        expected = """<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd"><root>
  <list>
    <item>
       <name>Name</name>
       <description>Description</description>
    </item>
  </list>
</root>"""
        self.assertNormalizedXMLEqual(actual, expected)

    def test_write_simple_xml_fragment_kills_doctype_and_declaration(self):
        root = self._parse(_SIMPLE_XML)
        from supervisor.templating import doctype
        actual = self._write_xml(root, declaration=True,
                                 doctype=doctype.xhtml, fragment=True)
        expected = """<root>
  <list>
    <item>
       <name>Name</name>
       <description>Description</description>
    </item>
  </list>
</root>"""
        self.assertNormalizedXMLEqual(actual, expected)

    def test_write_simple_xhtml_override_encoding(self):
        root = self._parse(_SIMPLE_XHTML)
        actual = self._write_xhtml(root, encoding="latin-1", declaration=True)
        expected = """<?xml version="1.0" encoding="latin-1"?><!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd"><html><body>Hello!</body></html>"""
        self.assertNormalizedXMLEqual(actual, expected)

    def test_write_simple_xhtml_as_fragment(self):
        root = self._parse(_SIMPLE_XHTML)
        actual = self._write_xhtml(root, fragment=True)
        expected = """<html><body>Hello!</body></html>"""
        self.assertNormalizedXMLEqual(actual, expected)

    def test_write_simple_xhtml_with_doctype(self):
        root = self._parse(_SIMPLE_XHTML)
        from supervisor.templating import doctype
        actual = self._write_xhtml(root, doctype=doctype.xhtml)
        expected = """<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd"><html><body>Hello!</body></html>"""
        self.assertNormalizedXMLEqual(actual, expected)

    def test_write_simple_xhtml_doctype_nodeclaration(self):
        root = self._parse(_SIMPLE_XHTML)
        from supervisor.templating import doctype
        actual = self._write_xhtml(root, declaration=False,
                                 doctype=doctype.xhtml)
        expected = """<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd"><html><body>Hello!</body></html>"""
        self.assertNormalizedXMLEqual(actual, expected)

    def test_write_simple_xhtml_fragment_kills_doctype_and_declaration(self):
        root = self._parse(_SIMPLE_XHTML)
        from supervisor.templating import doctype
        actual = self._write_xhtml(root, declaration=True,
                                 doctype=doctype.xhtml, fragment=True)
        expected = """<html><body>Hello!</body></html>"""
        self.assertNormalizedXMLEqual(actual, expected)

    def test_write_simple_xhtml_as_html_fragment(self):
        root = self._parse(_SIMPLE_XHTML)
        actual = self._write_html(root, fragment=True)
        expected = """<html><body>Hello!</body></html>"""
        self.assertNormalizedXMLEqual(actual, expected)

    def test_write_simple_xhtml_with_doctype_as_html(self):
        root = self._parse(_SIMPLE_XHTML)
        actual = self._write_html(root)
        expected = """
<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN" "http://www.w3.org/TR/html4/loose.dtd">
<html><body>Hello!</body></html>"""
        self.assertNormalizedXMLEqual(actual, expected)

    def test_write_simple_xhtml_as_html_new_doctype(self):
        root = self._parse(_SIMPLE_XHTML)
        from supervisor.templating import doctype
        actual = self._write_html(root, doctype=doctype.html_strict)
        expected = """
<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01//EN" "http://www.w3.org/TR/html4/strict.dtd">
<html><body>Hello!</body></html>"""
        self.assertNormalizedXMLEqual(actual, expected)

    def test_unknown_entity(self):
        # exception thrown may vary by python or expat version
        from xml.parsers import expat
        self.assertRaises((expat.error, SyntaxError), self._parse,
                          '<html><head></head><body>&fleeb;</body></html>')

    def test_content_nostructure(self):
        root = self._parse(_SIMPLE_XML)
        D = root.findmeld('description')
        D.content('description &<foo>&amp;<bar>', structure=False)
        actual = self._write_xml(root)
        expected = """<?xml version="1.0"?>
        <root>
        <list>
        <item>
        <name>Name</name>
          <description>description &amp;&lt;foo>&amp;&lt;bar></description>
        </item>
        </list>
        </root>"""
        self.assertNormalizedXMLEqual(actual, expected)

    def test_content_structure(self):
        root = self._parse(_SIMPLE_XML)
        D = root.findmeld('description')
        D.content('description &<foo> <bar>', structure=True)
        actual = self._write_xml(root)
        expected = """<?xml version="1.0"?>
        <root>
        <list>
        <item>
        <name>Name</name>
          <description>description &<foo> <bar></description>
        </item>
        </list>
        </root>"""
        self.assertNormalizedXMLEqual(actual, expected)

    def test_replace_nostructure(self):
        root = self._parse(_SIMPLE_XML)
        D = root.findmeld('description')
        D.replace('description &<foo>&amp;<bar>', structure=False)
        actual = self._write_xml(root)
        expected = """<?xml version="1.0"?>
        <root>
        <list>
        <item>
        <name>Name</name>
          description &amp;&lt;foo>&amp;&lt;bar>
        </item>
        </list>
        </root>"""
        self.assertNormalizedXMLEqual(actual, expected)

    def test_replace_structure(self):
        root = self._parse(_SIMPLE_XML)
        D = root.findmeld('description')
        D.replace('description &<foo> <bar>', structure=True)
        actual = self._write_xml(root)
        expected = """<?xml version="1.0"?>
        <root>
        <list>
        <item>
        <name>Name</name>
          description &<foo> <bar>
        </item>
        </list>
        </root>"""
        self.assertNormalizedXMLEqual(actual, expected)

    def test_escape_cdata(self):
        from supervisor.compat import as_bytes
        from supervisor.templating import _escape_cdata
        a = ('< > &lt;&amp; &&apos; && &foo "" '
             'http://www.example.com?foo=bar&bang=baz &#123;')
        self.assertEqual(
            as_bytes('&lt; > &lt;&amp; &amp;&apos; &amp;&amp; &amp;foo "" '
                     'http://www.example.com?foo=bar&amp;bang=baz &#123;',
                     encoding='latin1'),
            _escape_cdata(a))

    def test_escape_cdata_unicodeerror(self):
        from supervisor.templating import _escape_cdata
        from supervisor.compat import as_bytes
        from supervisor.compat import as_string
        a = as_string(as_bytes('\x80', encoding='latin1'), encoding='latin1')
        self.assertEqual(as_bytes('&#128;', encoding='latin1'),
                         _escape_cdata(a, 'ascii'))

    def test_escape_attrib(self):
        from supervisor.templating import _escape_attrib
        from supervisor.compat import as_bytes
        a = ('< > &lt;&amp; &&apos; && &foo "" '
             'http://www.example.com?foo=bar&bang=baz &#123;')
        self.assertEqual(
            as_bytes('&lt; > &lt;&amp; &amp;&apos; '
                     '&amp;&amp; &amp;foo &quot;&quot; '
                     'http://www.example.com?foo=bar&amp;bang=baz &#123;',
                     encoding='latin1'),
            _escape_attrib(a, None))

    def test_escape_attrib_unicodeerror(self):
        from supervisor.templating import _escape_attrib
        from supervisor.compat import as_bytes
        from supervisor.compat import as_string
        a = as_string(as_bytes('\x80', encoding='latin1'), encoding='latin1')
        self.assertEqual(as_bytes('&#128;', encoding='latin1'),
                         _escape_attrib(a, 'ascii'))

def normalize_html(s):
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"/>", ">", s)
    return s

def normalize_xml(s):
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"(?s)\s+<", "<", s)
    s = re.sub(r"(?s)>\s+", ">", s)
    return s

def test_suite():
    return unittest.findTestCases(sys.modules[__name__])

def main():
    unittest.main(defaultTest='test_suite')

if __name__ == '__main__':
    main()
