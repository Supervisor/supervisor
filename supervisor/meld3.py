import os
import re
import sys
from supervisor.py3compat import *
from supervisor import read_file

if PY3:
    import html.entities as htmlentitydefs
    from io import StringIO
    def encode(text, encoding):
        return text
else:
    #noinspection PyUnresolvedReferences
    import htmlentitydefs
    #noinspection PyUnresolvedReferences
    from StringIO import StringIO
    def encode(text, encoding):
        return text.encode(encoding)

try:
    from elementtree.ElementTree import TreeBuilder
    from elementtree.ElementTree import XMLTreeBuilder
    from elementtree.ElementTree import Comment
    from elementtree.ElementTree import ProcessingInstruction
    from elementtree.ElementTree import QName
    from elementtree.ElementTree import _raise_serialization_error
    from elementtree.ElementTree import _namespace_map
    from elementtree.ElementTree import _encode_entity
    from elementtree.ElementTree import fixtag
    from elementtree.ElementTree import parse as et_parse
    from elementtree.ElementTree import ElementPath
except ImportError:
    from xml.etree.ElementTree import TreeBuilder
    from xml.etree.ElementTree import XMLTreeBuilder
    from xml.etree.ElementTree import Comment
    from xml.etree.ElementTree import ProcessingInstruction
    from xml.etree.ElementTree import QName
    from xml.etree.ElementTree import _raise_serialization_error
    from xml.etree.ElementTree import _namespace_map
    from xml.etree.ElementTree import XMLParser
    try:
        from xml.etree.ElementTree import _encode_entity
    except ImportError:
        def _encode_entity(s): return s
    from xml.etree.ElementTree import parse as et_parse
    from xml.etree.ElementTree import ElementPath

    try:
        from xml.etree.ElementTree import fixtag
    except:
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
        


# HTMLTreeBuilder does not exist in python 2.5 standard elementtree
try:
    #noinspection PyUnresolvedReferences
    from HTMLParser import HTMLParser
except ImportError:
    from html.parser import HTMLParser
AUTOCLOSE = "p", "li", "tr", "th", "td", "head", "body"
IGNOREEND = "img", "hr", "meta", "link", "br"
is_not_ascii = lambda s: False if PY3 else re.compile(eval(r'u"[\u0080-\uffff]"')).search

# replace element factory
def Replace(text, structure=False):
    element = _MeldElementInterface(Replace, {})
    element.text = text
    element.structure = structure
    return element

class IO:
    def __init__(self):
        self.data = ""

    def write(self, data):
        self.data += data

    def getvalue(self):
        return self.data

    def clear(self):
        self.data = ""

class PyHelper:
    def findmeld(self, node, name, default=None):
        iterator = self.getiterator(node)
        for element in iterator:
            val = element.attrib.get(_MELD_ID)
            if val == name:
                return element
        return default

    def clone(self, node, parent=None):
        # NOTE: this is not implemented by the C version (it used to be
        # but I don't want to maintain it)
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

pyhelper = PyHelper()

try:
    import cmeld3 as chelper
except ImportError:
    chelper = None

if chelper and not os.getenv('MELD3_PYIMPL'):
    helper = chelper
else:
    helper = pyhelper

_MELD_NS_URL  = 'http://www.plope.com/software/meld3'
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
    Replace = [Replace] # this is used by C code

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
        # we ignore any tag= passed in to us, because it's too painful
        # to support in our C version
        return helper.getiterator(self)

    # overrides to support parent pointers and factories

    def __setitem__(self, index, element):
        if isinstance(index, slice):
            for e in element:
                e.parent = self
        else:
            element.parent = self
        self._children[index] = element

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
        del self._children[index]

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
        support dictionary-like operand (sequence operand doesn't seem
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
            if not isinstance(k, basestring):
                raise ValueError('do not set non-stringtype as key: %s' % k)
            if not isinstance(v, basestring):
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
        return ''.join(data)
        
    def write_xml(self, file, encoding=None, doctype=None,
                  fragment=False, declaration=True, pipeline=False):
        """ Write XML to 'file' (which can be a filename or file-like object)

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
        need_close = False
        if not hasattr(file, "write"):
            file = open(file, "wb")
            need_close = True
        data = self.write_xmlstring(encoding, doctype, fragment, declaration,
                                    pipeline)
        file.write(data)
        if need_close:
            file.close()

    def write_htmlstring(self, encoding=None, doctype=doctype.html,
                         fragment=False):
        data = []
        write = data.append
        if encoding is None:
            encoding = 'utf8'
        if encoding in ('utf8', 'utf-8', 'latin-1', 'latin1',
                        'ascii'):
            # optimize for common dumb-American case (only encode once at
            # the end)
            if not fragment:
                if doctype:
                    _write_doctype(write, doctype)
            _write_html_no_encoding(write, self, {})
            joined = ''.join(data)
            return joined
        else:
            if not fragment:
                if doctype:
                    _write_doctype(write, doctype)
            _write_html(write, self, encoding, {})
            joined = ''.join(data)
            return joined

    def write_html(self, file, encoding=None, doctype=doctype.html,
                   fragment=False):
        """ Write HTML to 'file' (which can be a filename or file-like object)

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
        need_close = False
        if not hasattr(file, "write"):
            file = open(file, "wb")
            need_close = True
        page = self.write_htmlstring(encoding, doctype, fragment)
        file.write(page)
        if need_close:
            file.close()

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
        return ''.join(data)

    def write_xhtml(self, file, encoding=None, doctype=doctype.xhtml,
                    fragment=False, declaration=False, pipeline=False):
        """ Write XHTML to 'file' (which can be a filename or file-like object)

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
        # use a list as a collector, and only call the write method of
        # the file once we've collected all output (reduce function call
        # overhead)
        data = []
        write = data.append
        need_close = False
        if not hasattr(file, "write"):
            need_close = True
            file = open(file, "wb")
        page = self.write_xhtmlstring(encoding, doctype, fragment, declaration,
                                      pipeline)
        file.write(page)
        if need_close:
            file.close()
            
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
        return ''.join(data)

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
    def comment(self, data):
        self.start(Comment, {})
        self.data(data)
        self.end(Comment)
    def doctype(self, name, pubid, system):
        pass

class MeldParser(XMLTreeBuilder):

    """ A parser based on Fredrik's PIParser at
    http://effbot.org/zone/element-pi.htm.  It blithely ignores the
    case of a comment existing outside the root element and ignores
    processing instructions entirely.  We need to validate that there
    are no repeated meld id's in the source as well """
    
    def __init__(self, html=0, target=None):
        XMLTreeBuilder.__init__(self, html, target)
        # assumes ElementTree 1.2.X
        if not PY3:
            self._parser.CommentHandler = self.handle_comment
        self.meldids = {}

    def handle_comment(self, data):
        self._target.start(Comment, {})
        self._target.data(data)
        self._target.end(Comment)

    def _start(self, tag, attrib_in):
        # this is used by self._parser (an Expat parser) as
        # StartElementHandler but only if _start_list is not
        # provided... so why does this method exist?
        for key in attrib_in:
            if '{' + key == _MELD_ID:
                meldid = attrib_in[key]
                if self.meldids.get(meldid):
                    raise ValueError('Repeated meld id "%s" in source' %
                                       meldid)
                self.meldids[meldid] = 1
        return XMLTreeBuilder._start(self, tag, attrib_in)

    def _start_list(self, tag, attrib_in):
        # This is used by self._parser (an Expat parser)
        # as StartElementHandler.  attrib_in is a flat even-length
        # sequence of name, value pairs for all attributes.
        # See http://python.org/doc/lib/xmlparser-objects.html
        for i in range(0, len(attrib_in), 2):
            # For some reason, clark names are missing the leading '{'
            attrib = self._fixname(attrib_in[i])
            if _MELD_ID == attrib:
                meldid = attrib_in[i+1]
                if self.meldids.get(meldid):
                    raise ValueError('Repeated meld id "%s" in source' %
                                       meldid)
                self.meldids[meldid] = 1
        return XMLTreeBuilder._start_list(self, tag, attrib_in)

    def close(self):
        val = XMLTreeBuilder.close(self)
        self.meldids = {}
        return val

class HTMLMeldParser(HTMLParser):
    """ A mostly-cut-and-paste of ElementTree's HTMLTreeBuilder that
    does special meld3 things (like preserve comments and munge meld
    ids).  Subclassing is not possible due to private attributes. :-("""

    def __init__(self, builder=None, encoding=None):
        self.__stack = []
        if builder is None:
            builder = MeldTreeBuilder()
        self.builder = builder
        self.encoding = encoding or "iso-8859-1"
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
                encoding = dict(v.strip().partition('=')[0::2] for v in content.split(';')).get('charset')
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
        if 0 <= char < 128:
            self.builder.data(chr(char))
        else:
            self.builder.data(unichr(char))

    def handle_entityref(self, name):
        entity = htmlentitydefs.entitydefs.get(name)
        if entity:
            if len(entity) == 1:
                entity = ord(entity)
            else:
                entity = int(entity[2:-1])
            if 0 <= entity < 128:
                self.builder.data(chr(entity))
            else:
                self.builder.data(unichr(entity))
        else:
            self.unknown_entityref(name)

    def handle_data(self, data):
        if isinstance(data, type('')) and is_not_ascii(data):
            # convert to unicode, but only if necessary
            data = unicode(data, self.encoding, "ignore")
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
    """ Parse source (a file-like object) into an element tree.  If
    html is true, use a parser that can resolve somewhat ambiguous
    HTML into XHTML.  Otherwise use a 'normal' parser only."""
    builder = MeldTreeBuilder()
    parser = MeldParser(target=builder)
    return do_parse(source, parser)

def parse_html(source, encoding=None):
    builder = MeldTreeBuilder()
    parser = HTMLMeldParser(builder, encoding)
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
    " Write HTML to file """
    if encoding is None:
        encoding = 'utf-8'

    tag  = node.tag
    tail = node.tail
    text = node.text
    tail = node.tail

    to_write = ""

    if tag is Replace:
        if not node.structure:
            if cdata_needs_escaping(text):
                text = _escape_cdata(text)
        write(encode(text,encoding))

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

        to_write += "<%s" % encode(tag,encoding)

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
                    to_write += ' ' + encode(k,encoding)
                else:
                    v = attrib[k]
                    to_write += " %s=\"%s\"" % (k, v)
                        
        for k, v in xmlns_items:
            to_write += " %s=\"%s\"" % (k, v)
                    
        to_write += ">"

        if text is not None and text:
            if tag in _HTMLTAGS_NOESCAPE:
                to_write += encode(text,encoding)
            elif cdata_needs_escaping(text):
                to_write += _escape_cdata(text)
            else:
                to_write += encode(text,encoding)

        write(to_write)

        for child in node._children:
            if maxdepth is not None:
                depth += 1
                if depth < maxdepth:
                    _write_html(write, child, encoding, namespaces, depth,
                                maxdepth)
                elif depth == maxdepth and text:
                    write(' [...]\n')

            else:
                _write_html(write, child, encoding, namespaces, depth, maxdepth)

        if text or node._children or tag not in _HTMLTAGS_UNBALANCED:
            write("</" + encode(tag,encoding) + ">")

    if tail:
        if cdata_needs_escaping(tail):
            write(_escape_cdata(tail))
        else:
            write(encode(tail,encoding))

def _write_html_no_encoding(write, node, namespaces):
    """ Append HTML to string without any particular unicode encoding.
    We have a separate function for this due to the fact that encoding
    while recursing is very expensive if this will get serialized out to
    utf8 anyway (the encoding can happen afterwards).  We append to a string
    because it's faster than calling any 'write' or 'append' function."""

    tag  = node.tag
    tail = node.tail
    text = node.text
    tail = node.tail

    to_write = ""

    if tag is Replace:
        if not node.structure:
            if cdata_needs_escaping(text):
                text = _escape_cdata_noencoding(text)
        write(text)

    elif tag is Comment:
        if cdata_needs_escaping(text):
            text = _escape_cdata_noencoding(text)
        write('<!-- ' + text + ' -->')

    elif tag is ProcessingInstruction:
        if cdata_needs_escaping(text):
            text = _escape_cdata_noencoding(text)
        write('<!-- ' + text + ' -->')

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

        to_write += "<" + tag

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
                    to_write += ' ' + k
                else:
                    v = attrib[k]
                    to_write += " %s=\"%s\"" % (k, v)
                        
        for k, v in xmlns_items:
            to_write += " %s=\"%s\"" % (k, v)
                    
        to_write += ">"

        if text is not None and text:
            if tag in _HTMLTAGS_NOESCAPE:
                to_write += text
            elif cdata_needs_escaping(text):
                to_write += _escape_cdata_noencoding(text)
            else:
                to_write += text

        write(to_write)

        for child in node._children:
            _write_html_no_encoding(write, child, namespaces)

        if text or node._children or tag not in _HTMLTAGS_UNBALANCED:
            write("</" + tag  + ">")

    if tail:
        if cdata_needs_escaping(tail):
            write(_escape_cdata_noencoding(tail))
        else:
            write(tail)

def _write_xml(write, node, encoding, namespaces, pipeline, xhtml=False):
    """ Write XML to a file """
    if encoding is None:
        encoding = 'utf-8'
    tag = node.tag
    if tag is Comment:
        write("<!-- %s -->" % _escape_cdata(node.text, encoding))
    elif tag is ProcessingInstruction:
        write("<?%s?>" % _escape_cdata(node.text, encoding))
    elif tag is Replace:
        if node.structure:
            # this may produce invalid xml
            write(encode(node.text,encoding))
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
        write("<" + encode(tag,encoding))
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
                write(" %s=\"%s\"" % (encode(k,encoding),
                                      _escape_attrib(v, encoding)))
            for k, v in xmlns_items:
                write(" %s=\"%s\"" % (encode(k,encoding),
                                      _escape_attrib(v, encoding)))
        if node.text or node._children:
            write(">")
            if node.text:
                write(_escape_cdata(node.text, encoding))
            for n in node._children:
                _write_xml(write, n, encoding, namespaces, pipeline, xhtml)
            write("</" + encode(tag,encoding) + ">")
        else:
            write(" />")
        for k, v in xmlns_items:
            del namespaces[v]
    if node.tail:
        write(_escape_cdata(node.tail, encoding))

# overrides to elementtree to increase speed and get entity quoting correct.

nonentity_re = re.compile('&(?!([#\w]*;))') # negative lookahead assertion

def _escape_cdata(text, encoding=None):
    # escape character data
    try:
        if encoding:
            try:
                text = encode(text,encoding)
            except UnicodeError:
                return _encode_entity(text)
        text = nonentity_re.sub('&amp;', text)
        text = text.replace("<", "&lt;")
        return text
    except (TypeError, AttributeError):
        _raise_serialization_error(text)

def _escape_attrib(text, encoding=None):
    # escape attribute value
    try:
        if encoding:
            try:
                text = encode(text,encoding)
            except UnicodeError:
                return _encode_entity(text)
        # don't requote properly-quoted entities
        text = nonentity_re.sub('&amp;', text)
        text = text.replace("<", "&lt;")
        text = text.replace('"', "&quot;")
        return text
    except (TypeError, AttributeError):
        _raise_serialization_error(text)

def _escape_cdata_noencoding(text):
    # escape character data
    text = nonentity_re.sub('&amp;', text)
    text = text.replace("<", "&lt;")
    return text

def _escape_attrib_noencoding(text):
    # don't requote properly-quoted entities
    text = nonentity_re.sub('&amp;', text)
    text = text.replace("<", "&lt;")
    text = text.replace('"', "&quot;")
    return text

# utility functions

def _write_declaration(write, encoding):
    if not encoding:
        write('<?xml version="1.0"?>\n')
    else:
        write('<?xml version="1.0" encoding="%s"?>\n' % encoding)

def _write_doctype(write, doctype):
    try:
        name, pubid, system = doctype
    except (ValueError, TypeError):
        raise ValueError("doctype must be supplied as a 3-tuple in the form "
                           "(name, pubid, system) e.g. '%s'" % doctype.xhtml)
    write('<!DOCTYPE %s PUBLIC "%s" "%s">\n' % (name, pubid, system))

xml_decl_re = re.compile(r'<\?xml .*?\?>')
begin_tag_re = re.compile(r'<[^/?!]?\w+')
#'<!DOCTYPE %s PUBLIC "%s" "%s">' % doctype.html

def insert_doctype(data, doctype=doctype.xhtml):
    # jam an html doctype declaration into 'data' if it
    # doesn't already contain a doctype declaration
    match = xml_decl_re.search(data)
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
    match = begin_tag_re.search(data)
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

def search(name):
    if not "." in name:
        raise ValueError("unloadable datatype name: " + repr(name))
    components = name.split('.')
    start = components[0]
    g = globals()
    package = __import__(start, g, g)
    modulenames = [start]
    for component in components[1:]:
        modulenames.append(component)
        try:
            package = getattr(package, component)
        except AttributeError:
            n = '.'.join(modulenames)
            package = __import__(n, g, g, component)
    return package

def sample_mutator(root):
    values = []
    for thing in range(0, 20):
        values.append((str(thing), str(thing)))

    ob = root.findmeld('tr')
    for tr, (name, desc) in ob.repeat(values):
        tr.findmeld('td1').content(name)
        tr.findmeld('td2').content(desc)



if __name__ == '__main__':
    # call interactively by invoking meld3.py with a filename and
    # a dotted-python-path name to a mutator function that accepts a single
    # argument (the root), e.g.:
    #
    # python meld3.py sample.html meld3.sample_mutator
    #
    # the rendering will be sent to stdout
    import sys
    filename = sys.argv[1]
    try:
        mutator = sys.argv[2]
    except IndexError:
        mutator = None
#    import timeit
    root = parse_html(read_file(filename))
    io = StringIO()
    if mutator:
        mutator = search(mutator)
        mutator(root)
    root.write_html(io)
    sys.stdout.write(io.getvalue())

