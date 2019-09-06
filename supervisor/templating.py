# This file was originally based on the meld3 package version 2.0.0
# (https://pypi.org/project/meld3/2.0.0/).  The meld3 package is not
# called out separately in Supervisor's license or copyright files
# because meld3 had the same authors, copyright, and license as
# Supervisor at the time this file was bundled with Supervisor.

import email
import re

from xml.etree.ElementTree import (
    Comment,
    ElementPath,
    ProcessingInstruction,
    QName,
    TreeBuilder,
    XMLParser,
    parse as et_parse
    )

from supervisor.compat import (
    PY2,
    htmlentitydefs,
    HTMLParser,
    StringIO,
    StringTypes,
    unichr,
    as_bytes,
    as_string,
    )

AUTOCLOSE = "p", "li", "tr", "th", "td", "head", "body"
IGNOREEND = "img", "hr", "meta", "link", "br"
_BLANK = as_bytes('', encoding='latin1')
_SPACE = as_bytes(' ', encoding='latin1')
_EQUAL = as_bytes('=', encoding='latin1')
_QUOTE = as_bytes('"', encoding='latin1')
_OPEN_TAG_START = as_bytes("<", encoding='latin1')
_CLOSE_TAG_START = as_bytes("</", encoding='latin1')
_OPEN_TAG_END = _CLOSE_TAG_END = as_bytes(">", encoding='latin1')
_SELF_CLOSE = as_bytes(" />", encoding='latin1')
_OMITTED_TEXT = as_bytes(' [...]\n', encoding='latin1')
_COMMENT_START = as_bytes('<!-- ', encoding='latin1')
_COMMENT_END = as_bytes(' -->', encoding='latin1')
_PI_START = as_bytes('<?', encoding='latin1')
_PI_END = as_bytes('?>', encoding='latin1')
_AMPER_ESCAPED = as_bytes('&amp;', encoding='latin1')
_LT = as_bytes('<', encoding='latin1')
_LT_ESCAPED = as_bytes('&lt;', encoding='latin1')
_QUOTE_ESCAPED = as_bytes("&quot;", encoding='latin1')
_XML_PROLOG_BEGIN = as_bytes('<?xml version="1.0"', encoding='latin1')
_ENCODING = as_bytes('encoding', encoding='latin1')
_XML_PROLOG_END = as_bytes('?>\n', encoding='latin1')
_DOCTYPE_BEGIN = as_bytes('<!DOCTYPE', encoding='latin1')
_PUBLIC = as_bytes('PUBLIC', encoding='latin1')
_DOCTYPE_END = as_bytes('>\n', encoding='latin1')

if PY2:
    def encode(text, encoding):
        return text.encode(encoding)
else:
    def encode(text, encoding):
        if not isinstance(text, bytes):
            text = text.encode(encoding)
        return text

# replace element factory
def Replace(text, structure=False):
    element = _MeldElementInterface(Replace, {})
    element.text = text
    element.structure = structure
    return element

class PyHelper:
    def findmeld(self, node, name, default=None):
        iterator = self.getiterator(node)
        for element in iterator:
            val = element.attrib.get(_MELD_ID)
            if val == name:
                return element
        return default

    def clone(self, node, parent=None):
        element = _MeldElementInterface(node.tag, node.attrib.copy())
        element.text = node.text
        element.tail = node.tail
        element.structure = node.structure
        if parent is not None:
            # avoid calling self.append to reduce function call overhead
            parent._children.append(element)
            element.parent = parent
        for child in node._children:
            self.clone(child, element)
        return element

    def _bfclone(self, nodes, parent):
        L = []
        for node in nodes:
            element = _MeldElementInterface(node.tag, node.attrib.copy())
            element.parent = parent
            element.text = node.text
            element.tail = node.tail
            element.structure = node.structure
            if node._children:
                self._bfclone(node._children, element)
            L.append(element)
        parent._children = L

    def bfclone(self, node, parent=None):
        element = _MeldElementInterface(node.tag, node.attrib.copy())
        element.text = node.text
        element.tail = node.tail
        element.structure = node.structure
        element.parent = parent
        if parent is not None:
            parent._children.append(element)
        if node._children:
            self._bfclone(node._children, element)
        return element

    def getiterator(self, node, tag=None):
        nodes = []
        if tag == "*":
            tag = None
        if tag is None or node.tag == tag:
            nodes.append(node)
        for element in node._children:
            nodes.extend(self.getiterator(element, tag))
        return nodes

    def content(self, node, text, structure=False):
        node.text = None
        replacenode = Replace(text, structure)
        replacenode.parent = node
        replacenode.text = text
        replacenode.structure = structure
        node._children = [replacenode]

helper = PyHelper()

_MELD_NS_URL  = 'https://github.com/Supervisor/supervisor'
_MELD_PREFIX  = '{%s}' % _MELD_NS_URL
_MELD_LOCAL   = 'id'
_MELD_ID      = '%s%s' % (_MELD_PREFIX, _MELD_LOCAL)
_MELD_SHORT_ID = 'meld:%s' % _MELD_LOCAL
_XHTML_NS_URL = 'http://www.w3.org/1999/xhtml'
_XHTML_PREFIX = '{%s}' % _XHTML_NS_URL
_XHTML_PREFIX_LEN = len(_XHTML_PREFIX)


_marker = []

class doctype:
    # lookup table for ease of use in external code
    html_strict  = ('HTML', '-//W3C//DTD HTML 4.01//EN',
                    'http://www.w3.org/TR/html4/strict.dtd')
    html         = ('HTML', '-//W3C//DTD HTML 4.01 Transitional//EN',
                   'http://www.w3.org/TR/html4/loose.dtd')
    xhtml_strict = ('html', '-//W3C//DTD XHTML 1.0 Strict//EN',
                    'http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd')
    xhtml        = ('html', '-//W3C//DTD XHTML 1.0 Transitional//EN',
                    'http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd')

class _MeldElementInterface:
    parent = None
    attrib = None
    text   = None
    tail   = None
    structure = None

    # overrides to reduce MRU lookups
    def __init__(self, tag, attrib):
        self.tag = tag
        self.attrib = attrib
        self._children = []

    def __repr__(self):
        return "<MeldElement %s at %x>" % (self.tag, id(self))

    def __len__(self):
        return len(self._children)

    def __getitem__(self, index):
        return self._children[index]

    def __getslice__(self, start, stop):
        return self._children[start:stop]

    def getchildren(self):
        return self._children

    def find(self, path):
        return ElementPath.find(self, path)

    def findtext(self, path, default=None):
        return ElementPath.findtext(self, path, default)

    def findall(self, path):
        return ElementPath.findall(self, path)

    def clear(self):
        self.attrib.clear()
        self._children = []
        self.text = self.tail = None

    def get(self, key, default=None):
        return self.attrib.get(key, default)

    def set(self, key, value):
        self.attrib[key] = value

    def keys(self):
        return list(self.attrib.keys())

    def items(self):
        return list(self.attrib.items())

    def getiterator(self, *ignored_args, **ignored_kw):
        # we ignore any tag= passed in to us, originally because it was too
        # painfail to support in the old C extension, now for b/w compat
        return helper.getiterator(self)

    # overrides to support parent pointers and factories

    def __setitem__(self, index, element):
        if isinstance(index, slice):
            for e in element:
                e.parent = self
        else:
            element.parent = self

        self._children[index] = element

    # TODO: Can __setslice__ be removed now?
    def __setslice__(self, start, stop, elements):
        for element in elements:
            element.parent = self
        self._children[start:stop] = list(elements)

    def append(self, element):
        self._children.append(element)
        element.parent = self

    def insert(self, index, element):
        self._children.insert(index, element)
        element.parent = self

    def __delitem__(self, index):
        if isinstance(index, slice):
            for ob in self._children[index]:
                ob.parent = None
        else:
            self._children[index].parent = None

        ob = self._children[index]
        del self._children[index]

    # TODO: Can __delslice__ be removed now?
    def __delslice__(self, start, stop):
        obs = self._children[start:stop]
        for ob in obs:
            ob.parent = None
        del self._children[start:stop]

    def remove(self, element):
        self._children.remove(element)
        element.parent = None

    def makeelement(self, tag, attrib):
        return self.__class__(tag, attrib)

    # meld-specific

    def __mod__(self, other):
        """ Fill in the text values of meld nodes in tree; only
        support dictionarylike operand (sequence operand doesn't seem
        to make sense here)"""
        return self.fillmelds(**other)

    def fillmelds(self, **kw):
        """ Fill in the text values of meld nodes in tree using the
        keyword arguments passed in; use the keyword keys as meld ids
        and the keyword values as text that should fill in the node
        text on which that meld id is found.  Return a list of keys
        from **kw that were not able to be found anywhere in the tree.
        Never raises an exception. """
        unfilled = []
        for k in kw:
            node = self.findmeld(k)
            if node is None:
                unfilled.append(k)
            else:
                node.text = kw[k]
        return unfilled

    def fillmeldhtmlform(self, **kw):
        """ Perform magic to 'fill in' HTML form element values from a
        dictionary.  Unlike 'fillmelds', the type of element being
        'filled' is taken into consideration.

        Perform a 'findmeld' on each key in the dictionary and use the
        value that corresponds to the key to perform mutation of the
        tree, changing data in what is presumed to be one or more HTML
        form elements according to the following rules::

          If the found element is an 'input group' (its meld id ends
          with the string ':inputgroup'), set the 'checked' attribute
          on the appropriate subelement which has a 'value' attribute
          which matches the dictionary value.  Also remove the
          'checked' attribute from every other 'input' subelement of
          the input group.  If no input subelement's value matches the
          dictionary value, this key is treated as 'unfilled'.

          If the found element is an 'input type=text', 'input
          type=hidden', 'input type=submit', 'input type=password',
          'input type=reset' or 'input type=file' element, replace its
          'value' attribute with the value.

          If the found element is an 'input type=checkbox' or 'input
          type='radio' element, set its 'checked' attribute to true if
          the dict value is true, or remove its 'checked' attribute if
          the dict value is false.

          If the found element is a 'select' element and the value
          exists in the 'value=' attribute of one of its 'option'
          subelements, change that option's 'selected' attribute to
          true and mark all other option elements as unselected.  If
          the select element does not contain an option with a value
          that matches the dictionary value, do nothing and return
          this key as unfilled.

          If the found element is a 'textarea' or any other kind of
          element, replace its text with the value.

          If the element corresponding to the key is not found,
          do nothing and treat the key as 'unfilled'.

        Return a list of 'unfilled' keys, representing meld ids
        present in the dictionary but not present in the element tree
        or meld ids which could not be filled due to the lack of any
        matching subelements for 'select' nodes or 'inputgroup' nodes.
        """

        unfilled = []

        for k in kw:
            node = self.findmeld(k)

            if node is None:
                unfilled.append(k)
                continue

            val = kw[k]

            if k.endswith(':inputgroup'):
                # an input group is a list of input type="checkbox" or
                # input type="radio" elements that can be treated as a group
                # because they attempt to specify the same value

                found = []
                unfound = []

                for child in node.findall('input'):
                    input_type = child.attrib.get('type', '').lower()
                    if input_type not in ('checkbox', 'radio'):
                        continue

                    input_val = child.attrib.get('value', '')

                    if val == input_val:
                        found.append(child)
                    else:
                        unfound.append(child)

                if not found:
                    unfilled.append(k)

                else:
                    for option in found:
                        option.attrib['checked'] = 'checked'
                    for option in unfound:
                        try:
                            del option.attrib['checked']
                        except KeyError:
                            pass
            else:

                tag = node.tag.lower()

                if tag == 'input':

                    input_type = node.attrib.get('type', 'text').lower()

                    # fill in value attrib for most input types
                    if input_type in ('hidden', 'submit', 'text',
                                      'password', 'reset', 'file'):
                        node.attrib['value'] = val

                    # unless it's a checkbox or radio attribute, then we
                    # fill in its checked attribute
                    elif input_type in ('checkbox', 'radio'):
                        if val:
                            node.attrib['checked'] = 'checked'
                        else:
                            try:
                                del node.attrib['checked']
                            except KeyError:
                                pass
                    else:

                        unfilled.append(k)

                elif tag == 'select':
                    # if the node is a select node, we want to select
                    # the value matching val, otherwise it's unfilled

                    found = []
                    unfound = []

                    for option in node.findall('option'):
                        if option.attrib.get('value', '') == val:
                            found.append(option)
                        else:
                            unfound.append(option)
                    if not found:
                        unfilled.append(k)
                    else:
                        for option in found:
                            option.attrib['selected'] = 'selected'
                        for option in unfound:
                            try:
                                del option.attrib['selected']
                            except KeyError:
                                pass
                else:
                    node.text = kw[k]

        return unfilled

    def findmeld(self, name, default=None):
        """ Find a node in the tree that has a 'meld id' corresponding
        to 'name'. Iterate over all subnodes recursively looking for a
        node which matches.  If we can't find the node, return None."""
        # this could be faster if we indexed all the meld nodes in the
        # tree; we just walk the whole hierarchy now.
        result = helper.findmeld(self, name)
        if result is None:
            return default
        return result

    def findmelds(self):
        """ Find all nodes that have a meld id attribute and return
        the found nodes in a list"""
        return self.findwithattrib(_MELD_ID)

    def findwithattrib(self, attrib, value=None):
        """ Find all nodes that have an attribute named 'attrib'.  If
        'value' is not None, omit nodes on which the attribute value
        does not compare equally to 'value'. Return the found nodes in
        a list."""
        iterator = helper.getiterator(self)
        elements = []
        for element in iterator:
            attribval = element.attrib.get(attrib)
            if attribval is not None:
                if value is None:
                    elements.append(element)
                else:
                    if value == attribval:
                        elements.append(element)
        return elements

    # ZPT-alike methods
    def repeat(self, iterable, childname=None):
        """repeats an element with values from an iterable.  If
        'childname' is not None, repeat the element on which the
        repeat is called, otherwise find the child element with a
        'meld:id' matching 'childname' and repeat that.  The element
        is repeated within its parent element (nodes that are created
        as a result of a repeat share the same parent).  This method
        returns an iterable; the value of each iteration is a
        two-sequence in the form (newelement, data).  'newelement' is
        a clone of the template element (including clones of its
        children) which has already been seated in its parent element
        in the template. 'data' is a value from the passed in
        iterable.  Changing 'newelement' (typically based on values
        from 'data') mutates the element 'in place'."""
        if childname:
            element = self.findmeld(childname)
        else:
            element = self

        parent = element.parent
        # creating a list is faster than yielding a generator (py 2.4)
        L = []
        first = True
        for thing in iterable:
            if first is True:
                clone = element
            else:
                clone = helper.bfclone(element, parent)
            L.append((clone, thing))
            first = False
        return L

    def replace(self, text, structure=False):
        """ Replace this element with a Replace node in our parent with
        the text 'text' and return the index of our position in
        our parent.  If we have no parent, do nothing, and return None.
        Pass the 'structure' flag to the replace node so it can do the right
        thing at render time. """
        parent = self.parent
        i = self.deparent()
        if i is not None:
            # reduce function call overhead by not calliing self.insert
            node = Replace(text, structure)
            parent._children.insert(i, node)
            node.parent = parent
            return i

    def content(self, text, structure=False):
        """ Delete this node's children and append a Replace node that
        contains text.  Always return None.  Pass the 'structure' flag
        to the replace node so it can do the right thing at render
        time."""
        helper.content(self, text, structure)

    def attributes(self, **kw):
        """ Set attributes on this node. """
        for k, v in kw.items():
            # prevent this from getting to the parser if possible
            if not isinstance(k, StringTypes):
                raise ValueError('do not set non-stringtype as key: %s' % k)
            if not isinstance(v, StringTypes):
                raise ValueError('do not set non-stringtype as val: %s' % v)
            self.attrib[k] = kw[k]

    # output methods
    def write_xmlstring(self, encoding=None, doctype=None, fragment=False,
                        declaration=True, pipeline=False):
        data = []
        write = data.append
        if not fragment:
            if declaration:
                _write_declaration(write, encoding)
            if doctype:
                _write_doctype(write, doctype)
        _write_xml(write, self, encoding, {}, pipeline)
        return _BLANK.join(data)

    def write_xml(self, file, encoding=None, doctype=None,
                  fragment=False, declaration=True, pipeline=False):
        """ Write XML to 'file' (which can be a filename or filelike object)

        encoding    - encoding string (if None, 'utf-8' encoding is assumed)
                      Must be a recognizable Python encoding type.
        doctype     - 3-tuple indicating name, pubid, system of doctype.
                      The default is to prevent a doctype from being emitted.
        fragment    - True if a 'fragment' should be emitted for this node (no
                      declaration, no doctype).  This causes both the
                      'declaration' and 'doctype' parameters to become ignored
                      if provided.
        declaration - emit an xml declaration header (including an encoding
                      if it's not None).  The default is to emit the
                      doctype.
        pipeline    - preserve 'meld' namespace identifiers in output
                      for use in pipelining
        """
        if not hasattr(file, "write"):
            file = open(file, "wb")
        data = self.write_xmlstring(encoding, doctype, fragment, declaration,
                                    pipeline)
        file.write(data)

    def write_htmlstring(self, encoding=None, doctype=doctype.html,
                         fragment=False):
        data = []
        write = data.append
        if encoding is None:
            encoding = 'utf8'
        if not fragment:
            if doctype:
                _write_doctype(write, doctype)
        _write_html(write, self, encoding, {})
        joined = _BLANK.join(data)
        return joined

    def write_html(self, file, encoding=None, doctype=doctype.html,
                   fragment=False):
        """ Write HTML to 'file' (which can be a filename or filelike object)

        encoding    - encoding string (if None, 'utf-8' encoding is assumed).
                      Unlike XML output, this is not used in a declaration,
                      but it is used to do actual character encoding during
                      output.  Must be a recognizable Python encoding type.
        doctype     - 3-tuple indicating name, pubid, system of doctype.
                      The default is the value of doctype.html (HTML 4.0
                      'loose')
        fragment    - True if a "fragment" should be omitted (no doctype).
                      This overrides any provided "doctype" parameter if
                      provided.

        Namespace'd elements and attributes have their namespaces removed
        during output when writing HTML, so pipelining cannot be performed.

        HTML is not valid XML, so an XML declaration header is never emitted.
        """
        if not hasattr(file, "write"):
            file = open(file, "wb")
        page = self.write_htmlstring(encoding, doctype, fragment)
        file.write(page)

    def write_xhtmlstring(self, encoding=None, doctype=doctype.xhtml,
                          fragment=False, declaration=False, pipeline=False):
        data = []
        write = data.append
        if not fragment:
            if declaration:
                _write_declaration(write, encoding)
            if doctype:
                _write_doctype(write, doctype)
        _write_xml(write, self, encoding, {}, pipeline, xhtml=True)
        return _BLANK.join(data)

    def write_xhtml(self, file, encoding=None, doctype=doctype.xhtml,
                    fragment=False, declaration=False, pipeline=False):
        """ Write XHTML to 'file' (which can be a filename or filelike object)

        encoding    - encoding string (if None, 'utf-8' encoding is assumed)
                      Must be a recognizable Python encoding type.
        doctype     - 3-tuple indicating name, pubid, system of doctype.
                      The default is the value of doctype.xhtml (XHTML
                      'loose').
        fragment    - True if a 'fragment' should be emitted for this node (no
                      declaration, no doctype).  This causes both the
                      'declaration' and 'doctype' parameters to be ignored.
        declaration - emit an xml declaration header (including an encoding
                      string if 'encoding' is not None)
        pipeline    - preserve 'meld' namespace identifiers in output
                      for use in pipelining
        """
        if not hasattr(file, "write"):
            file = open(file, "wb")
        page = self.write_xhtmlstring(encoding, doctype, fragment, declaration,
                                      pipeline)
        file.write(page)

    def clone(self, parent=None):
        """ Create a clone of an element.  If parent is not None,
        append the element to the parent.  Recurse as necessary to create
        a deep clone of the element. """
        return helper.bfclone(self, parent)

    def deparent(self):
        """ Remove ourselves from our parent node (de-parent) and return
        the index of the parent which was deleted. """
        i = self.parentindex()
        if i is not None:
            del self.parent[i]
            return i

    def parentindex(self):
        """ Return the parent node index in which we live """
        parent = self.parent
        if parent is not None:
            return parent._children.index(self)

    def shortrepr(self, encoding=None):
        data = []
        _write_html(data.append, self, encoding, {}, maxdepth=2)
        return _BLANK.join(data)

    def diffmeld(self, other):
        """ Compute the meld element differences from this node (the
        source) to 'other' (the target).  Return a dictionary of
        sequences in the form {'unreduced:
               {'added':[], 'removed':[], 'moved':[]},
                               'reduced':
               {'added':[], 'removed':[], 'moved':[]},}
                               """
        srcelements = self.findmelds()
        tgtelements = other.findmelds()
        srcids = [ x.meldid() for x in srcelements ]
        tgtids = [ x.meldid() for x in tgtelements ]

        removed = []
        for srcelement in srcelements:
            if srcelement.meldid() not in tgtids:
                removed.append(srcelement)

        added = []
        for tgtelement in tgtelements:
            if tgtelement.meldid() not in srcids:
                added.append(tgtelement)

        moved = []
        for srcelement in srcelements:
            srcid = srcelement.meldid()
            if srcid in tgtids:
                i = tgtids.index(srcid)
                tgtelement = tgtelements[i]
                if not sharedlineage(srcelement, tgtelement):
                    moved.append(tgtelement)

        unreduced = {'added':added, 'removed':removed, 'moved':moved}

        moved_reduced = diffreduce(moved)
        added_reduced = diffreduce(added)
        removed_reduced = diffreduce(removed)

        reduced = {'moved':moved_reduced, 'added':added_reduced,
                   'removed':removed_reduced}

        return {'unreduced':unreduced,
                'reduced':reduced}

    def meldid(self):
        return self.attrib.get(_MELD_ID)

    def lineage(self):
        L = []
        parent = self
        while parent is not None:
            L.append(parent)
            parent = parent.parent
        return L

class MeldTreeBuilder(TreeBuilder):
    def __init__(self):
        TreeBuilder.__init__(self, element_factory=_MeldElementInterface)
        self.meldids = {}

    def start(self, tag, attrs):
        elem = TreeBuilder.start(self, tag, attrs)
        for key, value in attrs.items():
            if key == _MELD_ID:
                if value in self.meldids:
                    raise ValueError('Repeated meld id "%s" in source' %
                                     value)
                self.meldids[value] = 1
                break
        return elem

    def comment(self, data):
        self.start(Comment, {})
        self.data(data)
        self.end(Comment)

    def doctype(self, name, pubid, system):
        pass

class HTMLXMLParser(HTMLParser):
    """ A mostly-cut-and-paste of ElementTree's HTMLTreeBuilder that
    does special meld3 things (like preserve comments and munge meld
    ids).  Subclassing is not possible due to private attributes. :-("""

    def __init__(self, builder=None, encoding=None):
        self.__stack = []
        if builder is None:
            builder = MeldTreeBuilder()
        self.builder = builder
        self.encoding = encoding or "iso-8859-1"
        try:
            # ``convert_charrefs`` was added in Python 3.4.  Set it to avoid
            # "DeprecationWarning: The value of convert_charrefs will become
            # True in 3.5. You are encouraged to set the value explicitly."
            HTMLParser.__init__(self, convert_charrefs=False)
        except TypeError:
            HTMLParser.__init__(self)
        self.meldids = {}

    def close(self):
        HTMLParser.close(self)
        self.meldids = {}
        return self.builder.close()

    def handle_starttag(self, tag, attrs):
        if tag == "meta":
            # look for encoding directives
            http_equiv = content = None
            for k, v in attrs:
                if k == "http-equiv":
                    http_equiv = v.lower()
                elif k == "content":
                    content = v
            if http_equiv == "content-type" and content:
                # use email to parse the http header
                msg = email.message_from_string(
                    "%s: %s\n\n" % (http_equiv, content)
                    )
                encoding = msg.get_param("charset")
                if encoding:
                    self.encoding = encoding
        if tag in AUTOCLOSE:
            if self.__stack and self.__stack[-1] == tag:
                self.handle_endtag(tag)
        self.__stack.append(tag)
        attrib = {}
        if attrs:
            for k, v in attrs:
                if k == _MELD_SHORT_ID:
                    k = _MELD_ID
                    if self.meldids.get(v):
                        raise ValueError('Repeated meld id "%s" in source' %
                                         v)
                    self.meldids[v] = 1
                else:
                    k = k.lower()
                attrib[k] = v
        self.builder.start(tag, attrib)
        if tag in IGNOREEND:
            self.__stack.pop()
            self.builder.end(tag)

    def handle_endtag(self, tag):
        if tag in IGNOREEND:
            return
        lasttag = self.__stack.pop()
        if tag != lasttag and lasttag in AUTOCLOSE:
            self.handle_endtag(lasttag)
        self.builder.end(tag)

    def handle_charref(self, char):
        if char[:1] == "x":
            char = int(char[1:], 16)
        else:
            char = int(char)
        self.builder.data(unichr(char))

    def handle_entityref(self, name):
        entity = htmlentitydefs.entitydefs.get(name)
        if entity:
            if len(entity) == 1:
                entity = ord(entity)
            else:
                entity = int(entity[2:-1])
            self.builder.data(unichr(entity))
        else:
            self.unknown_entityref(name)

    def handle_data(self, data):
        if isinstance(data, bytes):
            data = as_string(data, self.encoding)
        self.builder.data(data)

    def unknown_entityref(self, name):
        pass # ignore by default; override if necessary

    def handle_comment(self, data):
        self.builder.start(Comment, {})
        self.builder.data(data)
        self.builder.end(Comment)

def do_parse(source, parser):
    root = et_parse(source, parser=parser).getroot()
    iterator = root.getiterator()
    for p in iterator:
        for c in p:
            c.parent = p
    return root

def parse_xml(source):
    """ Parse source (a filelike object) into an element tree.  If
    html is true, use a parser that can resolve somewhat ambiguous
    HTML into XHTML.  Otherwise use a 'normal' parser only."""
    builder = MeldTreeBuilder()
    parser = XMLParser(target=builder)
    return do_parse(source, parser)

def parse_html(source, encoding=None):
    builder = MeldTreeBuilder()
    parser = HTMLXMLParser(builder, encoding)
    return do_parse(source, parser)

def parse_xmlstring(text):
    source = StringIO(text)
    return parse_xml(source)

def parse_htmlstring(text, encoding=None):
    source = StringIO(text)
    return parse_html(source, encoding)

attrib_needs_escaping = re.compile(r'[&"<]').search
cdata_needs_escaping = re.compile(r'[&<]').search

def _both_case(mapping):
    # Add equivalent upper-case keys to mapping.
    lc_keys = list(mapping.keys())
    for k in lc_keys:
        mapping[k.upper()] = mapping[k]


_HTMLTAGS_UNBALANCED    = {'area':1, 'base':1, 'basefont':1, 'br':1, 'col':1,
                           'frame':1, 'hr':1, 'img':1, 'input':1, 'isindex':1,
                           'link':1, 'meta':1, 'param':1}
_both_case(_HTMLTAGS_UNBALANCED)

_HTMLTAGS_NOESCAPE      = {'script':1, 'style':1}
_both_case(_HTMLTAGS_NOESCAPE)

_HTMLATTRS_BOOLEAN      = {'selected':1, 'checked':1, 'compact':1, 'declare':1,
                           'defer':1, 'disabled':1, 'ismap':1, 'multiple':1,
                           'nohref':1, 'noresize':1, 'noshade':1, 'nowrap':1}
_both_case(_HTMLATTRS_BOOLEAN)

def _write_html(write, node, encoding, namespaces, depth=-1, maxdepth=None):
    """ Walk 'node', calling 'write' with bytes(?).
    """
    if encoding is None:
        encoding = 'utf-8'

    tag  = node.tag
    tail = node.tail
    text = node.text
    tail = node.tail

    to_write = _BLANK

    if tag is Replace:
        if not node.structure:
            if cdata_needs_escaping(text):
                text = _escape_cdata(text)
        write(encode(text, encoding))

    elif tag is Comment:
        if cdata_needs_escaping(text):
            text = _escape_cdata(text)
        write(encode('<!-- ' + text + ' -->', encoding))

    elif tag is ProcessingInstruction:
        if cdata_needs_escaping(text):
            text = _escape_cdata(text)
        write(encode('<!-- ' + text + ' -->', encoding))

    else:
        xmlns_items = [] # new namespaces in this scope
        try:
            if tag[:1] == "{":
                if tag[:_XHTML_PREFIX_LEN] == _XHTML_PREFIX:
                    tag = tag[_XHTML_PREFIX_LEN:]
                else:
                    tag, xmlns = fixtag(tag, namespaces)
                    if xmlns:
                        xmlns_items.append(xmlns)
        except TypeError:
            _raise_serialization_error(tag)

        to_write += _OPEN_TAG_START + encode(tag, encoding)

        attrib = node.attrib

        if attrib is not None:
            if len(attrib) > 1:
                attrib_keys = list(attrib.keys())
                attrib_keys.sort()
            else:
                attrib_keys = attrib
            for k in attrib_keys:
                try:
                    if k[:1] == "{":
                        continue
                except TypeError:
                    _raise_serialization_error(k)
                if k in _HTMLATTRS_BOOLEAN:
                    to_write += _SPACE + encode(k, encoding)
                else:
                    v = attrib[k]
                    to_write += _encode_attrib(k, v, encoding)

        for k, v in xmlns_items:
            to_write += _encode_attrib(k, v, encoding)

        to_write += _OPEN_TAG_END

        if text is not None and text:
            if tag in _HTMLTAGS_NOESCAPE:
                to_write += encode(text, encoding)
            elif cdata_needs_escaping(text):
                to_write += _escape_cdata(text)
            else:
                to_write += encode(text,encoding)

        write(to_write)

        for child in node._children:
            if maxdepth is not None:
                depth = depth + 1
                if depth < maxdepth:
                    _write_html(write, child, encoding, namespaces, depth,
                                maxdepth)
                elif depth == maxdepth and text:
                    write(_OMITTED_TEXT)

            else:
                _write_html(write, child, encoding, namespaces, depth, maxdepth)

        if text or node._children or tag not in _HTMLTAGS_UNBALANCED:
            write(_CLOSE_TAG_START + encode(tag, encoding) + _CLOSE_TAG_END)

    if tail:
        if cdata_needs_escaping(tail):
            write(_escape_cdata(tail))
        else:
            write(encode(tail,encoding))

def _write_xml(write, node, encoding, namespaces, pipeline, xhtml=False):
    """ Write XML to a file """
    if encoding is None:
        encoding = 'utf-8'
    tag = node.tag
    if tag is Comment:
        write(_COMMENT_START +
              _escape_cdata(node.text, encoding) +
              _COMMENT_END)
    elif tag is ProcessingInstruction:
        write(_PI_START +
              _escape_cdata(node.text, encoding) +
              _PI_END)
    elif tag is Replace:
        if node.structure:
            # this may produce invalid xml
            write(encode(node.text, encoding))
        else:
            write(_escape_cdata(node.text, encoding))
    else:
        if xhtml:
            if tag[:_XHTML_PREFIX_LEN] == _XHTML_PREFIX:
                tag = tag[_XHTML_PREFIX_LEN:]
        if node.attrib:
            items = list(node.attrib.items())
        else:
            items = []  # must always be sortable.
        xmlns_items = [] # new namespaces in this scope
        try:
            if tag[:1] == "{":
                tag, xmlns = fixtag(tag, namespaces)
                if xmlns:
                    xmlns_items.append(xmlns)
        except TypeError:
            _raise_serialization_error(tag)
        write(_OPEN_TAG_START + encode(tag, encoding))
        if items or xmlns_items:
            items.sort() # lexical order
            for k, v in items:
                try:
                    if k[:1] == "{":
                        if not pipeline:
                            if k == _MELD_ID:
                                continue
                        k, xmlns = fixtag(k, namespaces)
                        if xmlns: xmlns_items.append(xmlns)
                    if not pipeline:
                        # special-case for HTML input
                        if k == 'xmlns:meld':
                            continue
                except TypeError:
                    _raise_serialization_error(k)
                write(_encode_attrib(k, v, encoding))
            for k, v in xmlns_items:
                write(_encode_attrib(k, v, encoding))
        if node.text or node._children:
            write(_OPEN_TAG_END)
            if node.text:
                write(_escape_cdata(node.text, encoding))
            for n in node._children:
                _write_xml(write, n, encoding, namespaces, pipeline, xhtml)
            write(_CLOSE_TAG_START + encode(tag, encoding) + _CLOSE_TAG_END)
        else:
            write(_SELF_CLOSE)
        for k, v in xmlns_items:
            del namespaces[v]
    if node.tail:
        write(_escape_cdata(node.tail, encoding))

def _encode_attrib(k, v, encoding):
    return _BLANK.join((_SPACE,
                        encode(k, encoding),
                        _EQUAL,
                        _QUOTE,
                        _escape_attrib(v, encoding),
                        _QUOTE,
                       ))

# overrides to elementtree to increase speed and get entity quoting correct.

# negative lookahead assertion
_NONENTITY_RE = re.compile(as_bytes(r'&(?!([#\w]*;))', encoding='latin1'))

def _escape_cdata(text, encoding=None):
    # Return escaped character data as bytes.
    try:
        if encoding:
            try:
                encoded = encode(text, encoding)
            except UnicodeError:
                return _encode_entity(text)
        else:
            encoded = as_bytes(text, encoding='latin1')
        encoded = _NONENTITY_RE.sub(_AMPER_ESCAPED, encoded)
        encoded = encoded.replace(_LT, _LT_ESCAPED)
        return encoded
    except (TypeError, AttributeError):
        _raise_serialization_error(text)

def _escape_attrib(text, encoding):
    # Return escaped attribute value as bytes.
    try:
        if encoding:
            try:
                encoded = encode(text, encoding)
            except UnicodeError:
                return _encode_entity(text)
        else:
            encoded = as_bytes(text, encoding='latin1')
        # don't requote properly-quoted entities
        encoded = _NONENTITY_RE.sub(_AMPER_ESCAPED, encoded)
        encoded = encoded.replace(_LT, _LT_ESCAPED)
        encoded = encoded.replace(_QUOTE, _QUOTE_ESCAPED)
        return encoded
    except (TypeError, AttributeError):
        _raise_serialization_error(text)

# utility functions

def _write_declaration(write, encoding):
    # Write as bytes.
    if not encoding:
        write(_XML_PROLOG_BEGIN + _XML_PROLOG_END)
    else:
        write(_XML_PROLOG_BEGIN +
              _SPACE +
              _ENCODING +
              _EQUAL +
              _QUOTE +
              as_bytes(encoding, encoding='latin1') +
              _QUOTE +
              _XML_PROLOG_END)

def _write_doctype(write, doctype):
    # Write as bytes.
    try:
        name, pubid, system = doctype
    except (ValueError, TypeError):
        raise ValueError("doctype must be supplied as a 3-tuple in the form "
                         "(name, pubid, system) e.g. '%s'" % doctype.xhtml)
    write(_DOCTYPE_BEGIN + _SPACE + as_bytes(name, encoding='latin1') +
          _SPACE + _PUBLIC + _SPACE +
          _QUOTE + as_bytes(pubid, encoding='latin1') + _QUOTE + _SPACE +
          _QUOTE + as_bytes(system, encoding='latin1') + _QUOTE +
          _DOCTYPE_END)

_XML_DECL_RE = re.compile(r'<\?xml .*?\?>')
_BEGIN_TAG_RE = re.compile(r'<[^/?!]?\w+')

def insert_doctype(data, doctype=doctype.xhtml):
    # jam an html doctype declaration into 'data' if it
    # doesn't already contain a doctype declaration
    match = _XML_DECL_RE.search(data)
    dt_string = '<!DOCTYPE %s PUBLIC "%s" "%s">' % doctype
    if match is not None:
        start, end = match.span(0)
        before = data[:start]
        tag = data[start:end]
        after = data[end:]
        return before + tag + dt_string + after
    else:
        return dt_string + data

def insert_meld_ns_decl(data):
    match = _BEGIN_TAG_RE.search(data)
    if match is not None:
        start, end = match.span(0)
        before = data[:start]
        tag = data[start:end] + ' xmlns:meld="%s"' % _MELD_NS_URL
        after = data[end:]
        data =  before + tag + after
    return data

def prefeed(data, doctype=doctype.xhtml):
    if data.find('<!DOCTYPE') == -1:
        data = insert_doctype(data, doctype)
    if data.find('xmlns:meld') == -1:
        data = insert_meld_ns_decl(data)
    return data

def sharedlineage(srcelement, tgtelement):
    srcparent = srcelement.parent
    tgtparent = tgtelement.parent
    srcparenttag = getattr(srcparent, 'tag', None)
    tgtparenttag = getattr(tgtparent, 'tag', None)
    if srcparenttag != tgtparenttag:
        return False
    elif tgtparenttag is None and srcparenttag is None:
        return True
    elif tgtparent and srcparent:
        return sharedlineage(srcparent, tgtparent)
    return False

def diffreduce(elements):
    # each element in 'elements' should all have non-None meldids, and should
    # be preordered in depth-first traversal order
    reduced = []
    for element in elements:
        parent = element.parent
        if parent is None:
            reduced.append(element)
            continue
        if parent in reduced:
            continue
        reduced.append(element)
    return reduced

def intersection(S1, S2):
    L = []
    for element in S1:
        if element in S2:
            L.append(element)
    return L

def melditerator(element, meldid=None, _MELD_ID=_MELD_ID):
    nodeid = element.attrib.get(_MELD_ID)
    if nodeid is not None:
        if meldid is None or nodeid == meldid:
            yield element
    for child in element._children:
        for el2 in melditerator(child, meldid):
            nodeid = el2.attrib.get(_MELD_ID)
            if nodeid is not None:
                if meldid is None or nodeid == meldid:
                    yield el2

#-----------------------------------------------------------------------------
# Begin fork from Python 2.6.8 stdlib:
#       - xml.elementtree.ElementTree._raise_serialization_error
#       - xml.elementtree.ElementTree._encode_entity
#       - xml.elementtree.ElementTree._namespace_map
#       - xml.elementtree.ElementTree.fixtag
#-----------------------------------------------------------------------------

_NON_ASCII_MIN = as_string('\xc2\x80', 'utf-8')        # u'\u0080'
_NON_ASCII_MAX = as_string('\xef\xbf\xbf', 'utf-8')    # u'\uffff'

_escape_map = {
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
}

_namespace_map = {
    # "well-known" namespace prefixes
    "http://www.w3.org/XML/1998/namespace": "xml",
    "http://www.w3.org/1999/xhtml": "html",
    "http://www.w3.org/1999/02/22-rdf-syntax-ns#": "rdf",
    "http://schemas.xmlsoap.org/wsdl/": "wsdl",
}

def _encode(s, encoding):
    try:
        return s.encode(encoding)
    except AttributeError:
        return s

def _raise_serialization_error(text):
    raise TypeError(
        "cannot serialize %r (type %s)" % (text, type(text).__name__)
        )

_pattern = None
def _encode_entity(text):
    # map reserved and non-ascii characters to numerical entities
    global _pattern
    if _pattern is None:
        _ptxt = r'[&<>\"' + _NON_ASCII_MIN + '-' + _NON_ASCII_MAX + ']+'
        #_pattern = re.compile(eval(r'u"[&<>\"\u0080-\uffff]+"'))
        _pattern = re.compile(_ptxt)

    def _escape_entities(m):
        out = []
        append = out.append
        for char in m.group():
            text = _escape_map.get(char)
            if text is None:
                text = "&#%d;" % ord(char)
            append(text)
        return ''.join(out)
    try:
        return _encode(_pattern.sub(_escape_entities, text), "ascii")
    except TypeError:
        _raise_serialization_error(text)

def fixtag(tag, namespaces):
    # given a decorated tag (of the form {uri}tag), return prefixed
    # tag and namespace declaration, if any
    if isinstance(tag, QName):
        tag = tag.text
    namespace_uri, tag = tag[1:].split("}", 1)
    prefix = namespaces.get(namespace_uri)
    if prefix is None:
        prefix = _namespace_map.get(namespace_uri)
        if prefix is None:
            prefix = "ns%d" % len(namespaces)
        namespaces[namespace_uri] = prefix
        if prefix == "xml":
            xmlns = None
        else:
            xmlns = ("xmlns:%s" % prefix, namespace_uri)
    else:
        xmlns = None
    return "%s:%s" % (prefix, tag), xmlns

#-----------------------------------------------------------------------------
# End fork from Python 2.6.8 stdlib
#-----------------------------------------------------------------------------
