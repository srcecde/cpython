# This script generates a Python interface for an Apple Macintosh Manager.
# It uses the "bgen" package to generate C code.
# The function specifications are generated by scanning the mamager's header file,
# using the "scantools" package (customized for this particular manager).

import string

# Declarations that change for each manager
MACHEADERFILE = 'Lists.h'		# The Apple header file
MODNAME = '_List'				# The name of the module
OBJECTNAME = 'List'			# The basic name of the objects used here
KIND = 'Handle'				# Usually 'Ptr' or 'Handle'

# The following is *usually* unchanged but may still require tuning
MODPREFIX = 'List'			# The prefix for module-wide routines
OBJECTTYPE = "ListHandle"		# The C type used to represent them
OBJECTPREFIX = MODPREFIX + 'Obj'	# The prefix for object methods
INPUTFILE = string.lower(MODPREFIX) + 'gen.py' # The file generated by the scanner
OUTPUTFILE = MODNAME + "module.c"	# The file generated by this program

from macsupport import *

# Create the type objects
ListHandle = OpaqueByValueType("ListHandle", "ListObj")
ListRef = ListHandle # Obsolete, but used in Lists.h
Cell = Point
ListBounds = Rect
ListBounds_ptr = Rect_ptr

ListDefSpec = ListDefSpec_ptr = OpaqueType("ListDefSpec", "PyMac_BuildListDefSpec", "PyMac_GetListDefSpec")

VarOutBufferShortsize = VarHeapOutputBufferType('char', 'short', 's')	# (buf, &len)
InBufferShortsize = VarInputBufferType('char', 'short', 's')		# (buf, len)

RgnHandle = OpaqueByValueType("RgnHandle", "ResObj")
DataHandle = OpaqueByValueType("DataHandle", "ResObj")
Handle = OpaqueByValueType("Handle", "ResObj")
CGrafPtr = OpaqueByValueType("CGrafPtr", "GrafObj")
EventModifiers = Type("EventModifiers", "H")

includestuff = includestuff + """
#ifdef WITHOUT_FRAMEWORKS
#include <Lists.h>
#else
#include <Carbon/Carbon.h>
#endif

#ifdef USE_TOOLBOX_OBJECT_GLUE
extern PyObject *_ListObj_New(ListHandle);
extern int _ListObj_Convert(PyObject *, ListHandle *);

#define ListObj_New _ListObj_New
#define ListObj_Convert _ListObj_Convert
#endif

#if !ACCESSOR_CALLS_ARE_FUNCTIONS
#define GetListPort(list) ((CGrafPtr)(*(list))->port)
#define GetListVerticalScrollBar(list) ((*(list))->vScroll)
#define GetListHorizontalScrollBar(list) ((*(list))->hScroll)
#define GetListActive(list) ((*(list))->lActive)
#define GetListClickTime(list) ((*(list))->clikTime)
#define GetListRefCon(list) ((*(list))->refCon)
#define GetListDefinition(list) ((*(list))->listDefProc) /* XXX Is this indeed the same? */
#define GetListUserHandle(list) ((*(list))->userHandle)
#define GetListDataHandle(list) ((*(list))->cells)
#define GetListFlags(list) ((*(list))->listFlags)
#define GetListSelectionFlags(list) ((*(list))->selFlags)
#define SetListViewBounds(list, bounds) (((*(list))->rView) = *(bounds))

#define SetListPort(list, port) (((*(list))->port) = (GrafPtr)(port))
#define SetListCellIndent(list, ind) (((*(list))->indent) = *(ind))
#define SetListClickTime(list, time) (((*(list))->clikTime) = (time))
#define SetListLastClick(list, click) (((*(list)->lastClick) = *(click))
#define SetListRefCon(list, refcon) (((*(list))->refCon) = (refcon))
#define SetListUserHandle(list, handle) (((*(list))->userHandle) = (handle))
#define SetListFlags(list, flags) (((*(list))->listFlags) = (flags))
#define SetListSelectionFlags(list, flags) (((*(list))->selFlags) = (flags))

#endif

#define as_List(x) ((ListHandle)x)
#define as_Resource(lh) ((Handle)lh)

static ListDefUPP myListDefFunctionUPP;

"""

initstuff = initstuff + """
myListDefFunctionUPP = NewListDefUPP((ListDefProcPtr)myListDefFunction);

PyMac_INIT_TOOLBOX_OBJECT_NEW(ListHandle, ListObj_New);
PyMac_INIT_TOOLBOX_OBJECT_CONVERT(ListHandle, ListObj_Convert);
"""

class ListMethodGenerator(MethodGenerator):
	"""Similar to MethodGenerator, but has self as last argument"""

	def parseArgumentList(self, args):
		args, a0 = args[:-1], args[-1]
		t0, n0, m0 = a0
		if m0 != InMode:
			raise ValueError, "method's 'self' must be 'InMode'"
		self.itself = Variable(t0, "_self->ob_itself", SelfMode)
		FunctionGenerator.parseArgumentList(self, args)
		self.argumentList.append(self.itself)

class MyObjectDefinition(PEP253Mixin, GlobalObjectDefinition):
	# XXXX Should inherit from Resource
	getsetlist = [(
		'listFlags',
		'return Py_BuildValue("l", (long)GetListFlags(self->ob_itself) & 0xff);',
		'if (!PyArg_Parse(v, "B", &(*self->ob_itself)->listFlags)) return -1;',
		None,
		), (
		'selFlags',
		'return Py_BuildValue("l", (long)GetListSelectionFlags(self->ob_itself) & 0xff);',
		'if (!PyArg_Parse(v, "B", &(*self->ob_itself)->selFlags)) return -1;',
		None,
		), (
		'cellSize',
		'return Py_BuildValue("O&", PyMac_BuildPoint, (*self->ob_itself)->cellSize);',
		'if (!PyArg_Parse(v, "O&", PyMac_GetPoint, &(*self->ob_itself)->cellSize)) return -1;',
		None
		)]

	def outputStructMembers(self):
		ObjectDefinition.outputStructMembers(self)
		Output("PyObject *ob_ldef_func;")
		Output("int ob_must_be_disposed;")

	def outputCheckNewArg(self):
		Output("""if (itself == NULL) {
					PyErr_SetString(List_Error,"Cannot create null List");
					return NULL;
				}""")
				
	def outputInitStructMembers(self):
		ObjectDefinition.outputInitStructMembers(self)
		Output("it->ob_ldef_func = NULL;")
		Output("it->ob_must_be_disposed = 1;")
		Output("SetListRefCon(itself, (long)it);")

	def outputFreeIt(self, itselfname):
		Output("Py_XDECREF(self->ob_ldef_func);")
		Output("self->ob_ldef_func = NULL;")
		Output("SetListRefCon(self->ob_itself, (long)0);")
		Output("if (self->ob_must_be_disposed && %s) LDispose(%s);", itselfname, itselfname)
		
# From here on it's basically all boiler plate...

finalstuff = finalstuff + """
static void myListDefFunction(SInt16 message,
                       Boolean selected,
                       Rect *cellRect,
                       Cell theCell,
                       SInt16 dataOffset,
                       SInt16 dataLen,
                       ListHandle theList)  
{
	PyObject *listDefFunc, *args, *rv=NULL;
	ListObject *self;
	
	self = (ListObject*)GetListRefCon(theList);
	if (self == NULL || self->ob_itself != theList)
		return;  /* nothing we can do */
	listDefFunc = self->ob_ldef_func;
	if (listDefFunc == NULL)
		return;  /* nothing we can do */
	args = Py_BuildValue("hbO&O&hhO", message,
	                                  selected,
	                                  PyMac_BuildRect, cellRect,
	                                  PyMac_BuildPoint, theCell,
	                                  dataOffset,
	                                  dataLen,
	                                  self);
	if (args != NULL) {
		rv = PyEval_CallObject(listDefFunc, args);
		Py_DECREF(args);
	}
	if (rv == NULL) {
		PySys_WriteStderr("error in list definition callback:\\n");
		PyErr_Print();
	} else {
		Py_DECREF(rv);
	}
}
"""

# Create the generator groups and link them
module = MacModule(MODNAME, MODPREFIX, includestuff, finalstuff, initstuff)
object = MyObjectDefinition(OBJECTNAME, OBJECTPREFIX, OBJECTTYPE)
module.addobject(object)

# Create the generator classes used to populate the lists
Function = FunctionGenerator
Method = ListMethodGenerator

# Create and populate the lists
functions = []
methods = []
execfile(INPUTFILE)

# Function to convert any handle to a list and vv.
##f = Function(ListHandle, 'as_List', (Handle, 'h', InMode))
as_List_body = """
Handle h;
ListObject *l;
if (!PyArg_ParseTuple(_args, "O&", ResObj_Convert, &h))
	return NULL;
l = (ListObject *)ListObj_New(as_List(h));
l->ob_must_be_disposed = 0;
_res = Py_BuildValue("O", l);
return _res;
"""
f = ManualGenerator("as_List", as_List_body)
f.docstring = lambda: "(Resource)->List.\nReturns List object (which is not auto-freed!)"
functions.append(f)

f = Method(Handle, 'as_Resource', (ListHandle, 'lh', InMode))
methods.append(f)

# Manual generator for CreateCustomList, due to callback ideosyncracies
CreateCustomList_body = """\
Rect rView;
Rect dataBounds;
Point cellSize;

PyObject *listDefFunc;
ListDefSpec theSpec;
WindowPtr theWindow;
Boolean drawIt;
Boolean hasGrow;
Boolean scrollHoriz;
Boolean scrollVert;
ListHandle outList;

if (!PyArg_ParseTuple(_args, "O&O&O&(iO)O&bbbb",
                      PyMac_GetRect, &rView,
                      PyMac_GetRect, &dataBounds,
                      PyMac_GetPoint, &cellSize,
                      &theSpec.defType, &listDefFunc,
                      WinObj_Convert, &theWindow,
                      &drawIt,
                      &hasGrow,
                      &scrollHoriz,
                      &scrollVert))
	return NULL;


/* Carbon applications use the CreateCustomList API */ 
theSpec.u.userProc = myListDefFunctionUPP;
CreateCustomList(&rView,
                 &dataBounds,
                 cellSize,
                 &theSpec,
                 theWindow,
                 drawIt,
                 hasGrow,
                 scrollHoriz,
                 scrollVert,
                 &outList);


_res = ListObj_New(outList);
if (_res == NULL)
	return NULL;
Py_INCREF(listDefFunc);
((ListObject*)_res)->ob_ldef_func = listDefFunc;
return _res;\
"""

f = ManualGenerator("CreateCustomList", CreateCustomList_body);
f.docstring = lambda: "(Rect rView, Rect dataBounds, Point cellSize, ListDefSpec theSpec, WindowPtr theWindow, Boolean drawIt, Boolean hasGrow, Boolean scrollHoriz, Boolean scrollVert) -> (ListHandle outList)"
module.add(f)

# add the populated lists to the generator groups
# (in a different wordl the scan program would generate this)
for f in functions: module.add(f)
for f in methods: object.add(f)


# generate output (open the output file as late as possible)
SetOutputFileName(OUTPUTFILE)
module.generate()

