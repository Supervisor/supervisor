#include <Python.h>

/* fprintf(stderr, "%s:%s:%d\n", __FILE__,__FUNCTION__,__LINE__);
   fflush(stderr); */

static PyObject *PySTR__class__, *PySTR__dict__, *PySTR_children;
static PyObject *PySTRattrib, *PySTRparent, *PySTR_MELD_ID;
static PyObject *PySTRtag, *PySTRtext, *PySTRtail, *PySTRstructure;
static PyObject *PySTRReplace;

static PyObject *emptyattrs, *emptychildren = NULL;

static PyObject*
clone(PyObject *node, PyObject *parent)
{
    PyObject *klass;
    PyObject *children;
    PyObject *text;
    PyObject *tail;
    PyObject *tag;
    PyObject *attrib;
    PyObject *structure;
    PyObject *dict;

    PyObject *newdict;
    PyObject *newchildren;
    PyObject *attrib_copy;
    PyObject *element;

    if (!(klass = PyObject_GetAttr(node, PySTR__class__))) return NULL;
    if (!(dict = PyObject_GetAttr(node, PySTR__dict__))) return NULL;

    if (!(children = PyDict_GetItem(dict, PySTR_children))) return NULL;
    if (!(tag = PyDict_GetItem(dict, PySTRtag))) return NULL;
    if (!(attrib = PyDict_GetItem(dict, PySTRattrib))) return NULL;

    if (!(text = PyDict_GetItem(dict, PySTRtext))) {
	text = Py_None;
    }
    if (!(tail = PyDict_GetItem(dict, PySTRtail))) {
	tail = Py_None;
    }
    if (!(structure = PyDict_GetItem(dict, PySTRstructure))) {
	structure = Py_None;
    }

    Py_INCREF(text);
    Py_INCREF(tail);
    Py_INCREF(tag);
    Py_INCREF(structure);

    if (!(newdict = PyDict_New())) return NULL;
    if (!(newchildren = PyList_New(0))) return NULL;

    attrib_copy = PyDict_Copy(attrib);

    PyDict_SetItem(newdict, PySTR_children, newchildren);
    PyDict_SetItem(newdict, PySTRattrib, attrib_copy);
    PyDict_SetItem(newdict, PySTRtext, text);
    PyDict_SetItem(newdict, PySTRtail, tail);
    PyDict_SetItem(newdict, PySTRtag, tag);
    PyDict_SetItem(newdict, PySTRstructure, structure);
    
    /* element = self.__class__(self.tag, self.attrib.copy()) */
    /* element.tail = self.tail */
    /* element.text = self.text */

    if (!(element = PyInstance_NewRaw(klass, newdict))) return NULL;

    Py_DECREF(klass);
    Py_DECREF(dict);
 
    /* if parent is not None:
       parent._children.append(element)
       element.parent = parent */

    PyObject *pchildren;
    
    if (parent != Py_None) {
        if (!(pchildren=PyObject_GetAttr(parent, PySTR_children))) return NULL;
	if (PyList_Append(pchildren, element)) return NULL;
	if (PyObject_SetAttr(element, PySTRparent, parent)) return NULL;
    }

    /* for child in self._children:
       child.clone(element) */

    int len, i;
    len = PyList_Size(children);
    if (len < 0) return NULL;

    PyObject *child;

    for (i = 0; i < len; i++) {
	if (!(child = PyList_GetItem(children, i))) {
	    return NULL;
	}
	clone(child, element);
	}
    
    return element;

}

static PyObject*
clonehandler(PyObject *self, PyObject *args)
{
    PyObject *node, *parent;
	
    if (!PyArg_ParseTuple(args, "OO:clone", &node, &parent)) {
	return NULL;
    }
    
    return clone(node, parent);
}

static char clonehandler_doc[] =
"clone(node, parent=None)\n			\
\n\
Return a clone of the meld3 node named by node.  If parent is not None, \n\
append the clone to the parent.\n";

static PyObject*
bfclone(PyObject *nodes, PyObject *parent)
{

    PyObject *L;
    if (!(L = PyList_New(0))) return NULL;

    int len, i;

    if (!(PyList_Check(nodes))) {
	return NULL;
    }

    len = PyList_Size(nodes);

    if (len < 0) {
	return NULL;
    }

    for (i = 0; i < len; i++) {

	PyObject *node;

	if (!(node = PyList_GetItem(nodes, i))) {
	    return NULL;
	}

	PyObject *klass;
	PyObject *children;
	PyObject *text;
	PyObject *tail;
	PyObject *tag;
	PyObject *attrib;
	PyObject *structure;
	PyObject *dict;
	PyObject *newdict;
	PyObject *newchildren;
	PyObject *attrib_copy;
	PyObject *element;
	int childsize;

	if (!(klass = PyObject_GetAttr(node, PySTR__class__))) return NULL;
	if (!(dict = PyObject_GetAttr(node, PySTR__dict__))) return NULL;

	if (!(children = PyDict_GetItem(dict, PySTR_children))) return NULL;
	if (!(tag = PyDict_GetItem(dict, PySTRtag))) return NULL;
	if (!(attrib = PyDict_GetItem(dict, PySTRattrib))) return NULL;

	if (!(text = PyDict_GetItem(dict, PySTRtext))) {
	    text = Py_None;
	}
	if (!(tail = PyDict_GetItem(dict, PySTRtail))) {
	    tail = Py_None;
	}
	if (!(structure = PyDict_GetItem(dict, PySTRstructure))) {
	    structure = Py_None;
	}

	Py_INCREF(text);
	Py_INCREF(tail);
	Py_INCREF(tag);
	Py_INCREF(structure);

	if (!(newdict = PyDict_New())) return NULL;
	if (!(newchildren = PyList_New(0))) return NULL;

	attrib_copy = PyDict_Copy(attrib);

	PyDict_SetItem(newdict, PySTR_children, newchildren);
	PyDict_SetItem(newdict, PySTRattrib, attrib_copy);
	PyDict_SetItem(newdict, PySTRtext, text);
	PyDict_SetItem(newdict, PySTRtail, tail);
	PyDict_SetItem(newdict, PySTRtag, tag);
	PyDict_SetItem(newdict, PySTRstructure, structure);
	PyDict_SetItem(newdict, PySTRparent, parent);
    
	if (!(element = PyInstance_NewRaw(klass, newdict))) {
	    return NULL;
	}

	Py_DECREF(klass);
	Py_DECREF(dict);
 
	if (PyList_Append(L, element)) {
	    return NULL;
	}
	if (!PyList_Check(children)) return NULL;

	if ((childsize = PyList_Size(children)) < 0) {
	    return NULL;
	}
	else {
	    if (childsize > 0) {
		bfclone(children, element);
	    }
	}
    }

    if (PyObject_SetAttr(parent, PySTR_children, L)) return NULL;
    return parent;

}

static PyObject*
bfclonehandler(PyObject *self, PyObject *args)
{
    PyObject *node, *parent;
	
    if (!PyArg_ParseTuple(args, "OO:clone", &node, &parent)) {
	return NULL;
    }
    
    PyObject *klass;
    PyObject *children;
    PyObject *text;
    PyObject *tail;
    PyObject *tag;
    PyObject *attrib;
    PyObject *structure;
    PyObject *dict;
    PyObject *newdict;
    PyObject *newchildren;
    PyObject *attrib_copy;
    PyObject *element;
    
    if (!(klass = PyObject_GetAttr(node, PySTR__class__))) return NULL;
    if (!(dict = PyObject_GetAttr(node, PySTR__dict__))) return NULL;
    
    if (!(children = PyDict_GetItem(dict, PySTR_children))) return NULL;
    if (!(tag = PyDict_GetItem(dict, PySTRtag))) return NULL;
    if (!(attrib = PyDict_GetItem(dict, PySTRattrib))) return NULL;
    
    if (!(text = PyDict_GetItem(dict, PySTRtext))) {
	text = Py_None;
    }
    if (!(tail = PyDict_GetItem(dict, PySTRtail))) {
	tail = Py_None;
    }
    if (!(structure = PyDict_GetItem(dict, PySTRstructure))) {
	structure = Py_None;
    }
    
    Py_INCREF(text);
    Py_INCREF(tail);
    Py_INCREF(tag);
    Py_INCREF(structure);
    
    if (!(newdict = PyDict_New())) return NULL;
    if (!(newchildren = PyList_New(0))) return NULL;
    
    attrib_copy = PyDict_Copy(attrib);
    
    PyDict_SetItem(newdict, PySTR_children, newchildren);
    PyDict_SetItem(newdict, PySTRattrib, attrib_copy);
    PyDict_SetItem(newdict, PySTRtext, text);
    PyDict_SetItem(newdict, PySTRtail, tail);
    PyDict_SetItem(newdict, PySTRtag, tag);
    PyDict_SetItem(newdict, PySTRstructure, structure);
    PyDict_SetItem(newdict, PySTRparent, parent);
    
    if (!(element = PyInstance_NewRaw(klass, newdict))) return NULL;
    
    Py_DECREF(klass);
    Py_DECREF(dict);

    PyObject *pchildren;
    
    if (parent != Py_None) {
        if (!(pchildren=PyObject_GetAttr(parent, PySTR_children))) return NULL;
	if (PyList_Append(pchildren, element)) return NULL;

    }

    if (!(PyList_Check(children))) return NULL;
    
    if (PyList_Size(children) > 0) {
	if (bfclone(children, element) == NULL) {
	    return NULL;
	}
    }
    return element;
    
}

static char bfclonehandler_doc[] =
"bfclone(node, parent=None)\n			\
\n\
Return a clone of the meld3 node named by node (breadth-first).  If parent\n\
is not None, append the clone to the parent.\n";

static PyObject*
getiterator(PyObject *node, PyObject *list) {
    if (PyList_Append(list, node) == -1) {
	return NULL;
    }
    Py_INCREF(node);
    PyObject *children;
    PyObject *child;

    if (!(children = PyObject_GetAttr(node, PySTR_children))) {
	return NULL;
    }

    int len, i;
    len = PyList_Size(children);
    if (len < 0) {
	return NULL;
    }

    for (i = 0; i < len; i++) {
	if (!(child = PyList_GetItem(children, i))) {
	    return NULL;
	}
        getiterator(child, list);
	}
    
    return list;
}

static PyObject*
getiteratorhandler(PyObject *self, PyObject *args)
{
    PyObject *node;
	
    if (!PyArg_ParseTuple(args, "O:getiterator", &node)) {
	return NULL;
    }
    PyObject *list;
    PyObject *result;
    if (!(list = PyList_New(0))) {
	return NULL;
    }
    result = getiterator(node, list);
    if (result == NULL) {
	PyList_SetSlice(list, 0, PyList_GET_SIZE(list), (PyObject *)NULL);
	Py_DECREF(list);
    }
    return result;
}

static char getiteratorhandler_doc[] =
"getiterator(node)\n\
\n\
Returns an iterator for the node.\n";

static char* _MELD_ID = "{http://www.plope.com/software/meld3}id";
/*static PyObject *PySTR_MELD_ID = PyString_FromString(_MELD_ID);*/

static PyObject*
findmeld(PyObject *node, PyObject *name) {
    PyObject *attrib, *meldid, *result;
    if (!(attrib = PyObject_GetAttr(node, PySTRattrib))) return NULL;
    meldid = PyDict_GetItem(attrib, PySTR_MELD_ID);
    result = Py_None;

    if (meldid != NULL) {
	int compareresult = PyUnicode_Compare(meldid, name);
	if (compareresult == 0) {
	    result = node;
	}
    }

    if (result == Py_None) {
	int len, i;
	PyObject *children = PyObject_GetAttr(node, PySTR_children);
	len = PyList_Size(children);
	for (i = 0; i < len; i++) {
	    PyObject *child = PyList_GetItem(children, i);
	    Py_INCREF(child);
	    result = findmeld(child, name);
            if (result != Py_None) {
		break;
	    }
	    Py_DECREF(child);
	}
    }

    return result;
    
}

static PyObject*
findmeldhandler(PyObject *self, PyObject *args)
{
    PyObject *node, *name, *result;
	
    if (!PyArg_ParseTuple(args, "OO:findmeld", &node, &name)) {
	return NULL;
    }
    if (!(result = findmeld(node, name))) return NULL;
    Py_INCREF(result);
    return result;
}

static char findmeldhandler_doc[] =
"findmeld(node, meldid)\n\
\n\
Return a meld node or None.\n";

static PyObject*
contenthandler(PyObject *self, PyObject *args) {
    PyObject *node, *text, *structure;
	
    if (!PyArg_ParseTuple(args, "OOO:content", &node, &text, &structure)) {
	return NULL;
    }
    PyObject *replace = NULL;
    PyObject *replacenode  = NULL;
    PyObject *newchildren  = NULL;
    PyObject *newdict  = NULL;
    PyObject *klass  = NULL;

    if (!(klass = PyObject_GetAttr(node, PySTR__class__))) return NULL;
    if (!(replace = PyObject_GetAttr(node, PySTRReplace))) return NULL;
    if (!(replace = PyList_GetItem(replace, 0))) return NULL;

    PyObject_SetAttr(node, PySTRtext, Py_None);
    Py_INCREF(Py_None);

    if (!(newdict = PyDict_New())) return NULL;
    PyDict_SetItem(newdict, PySTRparent, node);
    Py_INCREF(node);
    
    if (PyDict_SetItem(newdict, PySTRattrib, emptyattrs) == -1) return NULL;
    Py_INCREF(emptyattrs);
    if (PyDict_SetItem(newdict, PySTRtext, text) == -1) return NULL;
    Py_INCREF(text);
    if (PyDict_SetItem(newdict, PySTRstructure, structure) == -1) return NULL;
    Py_INCREF(structure);
    if (PyDict_SetItem(newdict, PySTR_children, emptychildren) == -1) {
	return NULL;
    }
    Py_INCREF(emptychildren);
    if (PyDict_SetItem(newdict, PySTRtag, replace) == -1) return NULL;
    Py_INCREF(replace);

    if (!(replacenode = PyInstance_NewRaw(klass, newdict))) return NULL;

    if (!(newchildren = PyList_New(1))) return NULL;
    PyList_SET_ITEM(newchildren, 0, replacenode);
    Py_INCREF(replacenode);
    PyObject_SetAttr(node, PySTR_children, newchildren);

    return replacenode;
    
}

static char contenthandler_doc[] =
"content(node, text, structure)\n\
\n\
Add a content node to node.\n";

static PyMethodDef methods[] = {
    {"clone", clonehandler, METH_VARARGS, clonehandler_doc},
    {"bfclone", bfclonehandler, METH_VARARGS, bfclonehandler_doc},
    {"getiterator", getiteratorhandler, METH_VARARGS, getiteratorhandler_doc},
    {"findmeld", findmeldhandler, METH_VARARGS, findmeldhandler_doc},
    {"content", contenthandler, METH_VARARGS, contenthandler_doc},
    {NULL, NULL}
};

PyMODINIT_FUNC
initcmeld3(void) 
{
#define DEFINE_STRING(s) \
    if (!(PySTR##s = PyString_FromString(#s))) return 
    DEFINE_STRING(__class__); 
    DEFINE_STRING(__dict__); 
    DEFINE_STRING(_children);
    DEFINE_STRING(parent);
    DEFINE_STRING(tag);
    DEFINE_STRING(attrib);
    DEFINE_STRING(text);
    DEFINE_STRING(tail);
    DEFINE_STRING(structure);
    DEFINE_STRING(Replace);
#undef DEFINE_STRING
    PySTR_MELD_ID = PyString_FromString(_MELD_ID);
    if (!PySTR_MELD_ID) {
	return;
    }
    emptyattrs = PyDict_New();
    emptyattrs = PyDictProxy_New(emptyattrs);
    emptychildren = PyList_New(0);
    Py_InitModule3("cmeld3", methods,
		   "C helpers for meld3");
}
