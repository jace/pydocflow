# -*- coding: utf-8 -*-

"""
Docflow: Python Document Workflows
"""

__version__ = '0.3'

from functools import wraps
import weakref
try:
    from collections import OrderedDict
except ImportError:
    from ordereddict import OrderedDict


class WorkflowException(Exception):
    pass


class WorkflowStateException(WorkflowException):
    pass


class WorkflowTransitionException(WorkflowException):
    pass


class WorkflowPermissionException(WorkflowException):
    pass


_creation_order = 1


def _set_creation_order(instance):
    """
    Assign a '_creation_order' sequence to the given instance.

    This allows multiple instances to be sorted in order of creation
    (typically within a single thread; the counter is not particularly
    threadsafe).

    This code is from SQLAlchemy, available here:
    http://www.sqlalchemy.org/trac/browser/lib/sqlalchemy/util/langhelpers.py#L836

    Only recommended for use at app load time.
    """
    global _creation_order
    instance._creation_order = _creation_order
    _creation_order += 1


class WorkflowTransition(object):
    """
    Transition between states.
    """
    def __init__(self, f, name,
                title='',
                description='',
                category='',
                permission='',
                state_from=None,
                state_to=None,
                **kwargs):
        self.f = f
        self.name = name
        self.title = title
        self.description = description
        self.category = category
        self.permission = permission
        self.state_from = state_from
        self.state_to = state_to
        self.__dict__.update(kwargs)

    def __call__(self, *args, **kwargs):
        return self.f(*args, **kwargs)


class WorkflowState(object):
    """
    State in a workflow.
    """

    exception_state = WorkflowStateException
    exception_transition = WorkflowTransitionException
    exception_permission = WorkflowPermissionException

    def __init__(self, value, title=u'', description=u''):
        self.value = value
        self.values = [value]
        self.name = None  # Not named yet
        self.title = title
        self.description = description
        self._parent = None
        self._transitions = OrderedDict()
        _set_creation_order(self)

    def attach(self, workflow):
        """
        Attach this workflow state to a workflow instance.
        """
        # XXX: This isn't particularly efficient. There has to be a way to
        # wrap the existing object instead of copying it.
        newstate = self.__class__(self.value, self.title, self.description)
        newstate.name = self.name
        newstate._parent = weakref.ref(workflow)
        newstate._transitions = self._transitions
        return newstate

    def __repr__(self):
        return "<WorkflowState %s>" % repr(self.title)

    def __call__(self):
        if self._parent is None or self._parent() is None:
            raise self.exception_state("Unattached state")
        return self._parent()._getStateValue() == self.value

    def __eq__(self, other):
        return self.value == other.value

    def __ne__(self, other):
        return not self.__eq__(other)

    def transition(self, state_to, permission,
                   title='', description='', category='', **kwargs):
        """
        Decorator for transition functions.
        """
        def inner(f):
            @wraps(f)
            def decorated_function(workflow, *args, **kwargs):
                # Perform tests: is state correct? Is permission available?
                if workflow.state != self:
                    raise self.exception_transition("Incorrect state")
                if permission and (permission not in
                                   workflow.permissions()):
                    raise self.exception_permission(
                        "Permission not available")
                result = f(workflow, *args, **kwargs)
                workflow._setStateValue(state_to.value)
                return result

            # XXX: Doesn't this cause circular references?
            # We have states referring to each other.
            t = WorkflowTransition(decorated_function,
                name=f.__name__,
                title=title,
                description=description,
                category=category,
                permission=permission,
                state_from=self,
                state_to=state_to,
                **kwargs)
            # TODO: Allow transitions to be attached to more than one state_from
            self._transitions[f.__name__] = t
            return decorated_function
        return inner


class WorkflowStateGroup(WorkflowState):
    """
    Group of states in a workflow. The value parameter is a list of value
    tokens or WorklowState instances.
    """
    def __init__(self, value, title=u'', description=u''):
        value = list(value)  # Make a copy before editing
        for counter, item in enumerate(value):
            if isinstance(item, WorkflowState):
                value[counter] = item.value
        super(WorkflowStateGroup, self).__init__(value, title, description)
        self.values = value

    def __repr__(self):
        return '<WorkflowStateGroup %s>' % repr(self.title)

    def __call__(self):
        if self._parent is None or self._parent() is None:
            raise self.exception_state("Unattached state")
        return self._parent()._getStateValue() in self.value


class _InitDocumentWorkflow(type):
    def __new__(cls, name, bases, attrs):
        attrs['_is_document_workflow'] = True
        attrs['_name'] = name
        attrs['_states'] = {}  # state_name: object
        attrs['_state_groups'] = {}  # state_group: object
        attrs['_state_values'] = {}  # Reverse lookup: value to object
        # If any base class contains _states, _state_groups or _state_values,
        # extend them
        for base in bases:
            if hasattr(base,
                       '_is_document_workflow') and base._is_document_workflow:
                attrs['_states'].update(base._states)
                attrs['_state_groups'].update(base._state_groups)
                attrs['_state_values'].update(base._state_values)

        for statename, stateob in attrs.items():
            if isinstance(stateob, WorkflowState):
                stateob.name = statename
                if isinstance(stateob, WorkflowStateGroup):
                    attrs['_state_groups'][statename] = stateob
                else:
                    attrs['_states'][statename] = stateob
                    # A group doesn't have a single value, so don't add groups
                    attrs['_state_values'][stateob.value] = stateob

        attrs['_states_sorted'] = sorted(attrs['_states'].values(),
            key=lambda s: s._creation_order)
        return super(_InitDocumentWorkflow, cls).__new__(
            cls, name, bases, attrs)


class DocumentWorkflow(object):
    """
    Base class for document workflows.
    """
    __metaclass__ = _InitDocumentWorkflow

    #: Subclasses may override the exception that is raised
    exception_state = WorkflowStateException

    #: One of these attributes must be overridden by subclasses

    #: State is contained in an attribute on the document
    state_attr = None
    #: Or, state is contained in a key in the document
    state_key = None
    #: Or, state is retrieved or set via special methods.
    #: state_get accepts a document as parameter, and state_set
    #: takes a document and a value
    state_get = None
    state_set = None

    def __init__(self, document, context=None):
        self.document = document
        self.context = context
        self._state = None  # No default state yet
        state = self._getStateValue()
        if state not in self._state_values:
            raise self.exception_state("Unknown state")
        # Attach states to self. Make copy and iterate:
        # This code is used just to make it possible to test
        # if a state is active by calling it: workflow.draft(), etc
        for statename, stateob in list(self._states.items()):
            attached = stateob.attach(self)
            setattr(self, statename, attached)
            self._states[statename] = attached
            self._state_values[attached.value] = attached
        for statename, stateob in list(self._state_groups.items()):
            attached = stateob.attach(self)
            setattr(self, statename, attached)
            self._state_groups[statename] = attached

    def __repr__(self):
        return '<Workflow %s>' % self._name

    @classmethod
    def _getStateValueInner(cls, document):
        # Get the state value from document
        if cls.state_attr:
            try:
                return getattr(document, cls.state_attr)
            except AttributeError:
                raise cls.exception_state("Unknown state")
        elif cls.state_key:
            try:
                return document[cls.state_key]
            except:
                raise cls.exception_state("Unknown state")
        elif cls.state_get:
            return cls.state_get(document)
        else:
            raise cls.exception_state("State cannot be read")

    def _getStateValue(self):
        return self._getStateValueInner(self.document)

    def _setStateValue(self, value):
        # Set state value on document
        if self.state_attr:
            setattr(self.document, self.state_attr, value)
        elif self.state_key:
            self.document[self.state_key] = value
        elif self.state_set:
            self.state_set(self.document, value)
        else:
            raise self.exception_state("State cannot be changed")

    @property
    def state(self):
        return self._state_values[self._getStateValue()]

    @classmethod
    def states(cls):
        """
        All states, sorted.
        """
        return list(cls._states_sorted)  # Make a shallow copy

    def permissions(self):
        """
        Permissions available in the current context. This method must be
        overridden by subclasses.
        """
        return []

    def transitions(self):
        """
        Transitions available in the current state and context.
        """
        permissions = self.permissions()
        result = OrderedDict()
        for k, v in self.state._transitions.iteritems():
            if v.permission is None or v.permission in permissions:
                result[k] = v
        return result

    @classmethod
    def apply_on(cls, docclass):
        """Apply workflow on specified document class."""
        def workflow(self):
            """Return a workflow wrapper for this document."""
            # Workflows can be re-instantiated anytime because they don't store
            # any data on the workflow object. All storage is in the document.
            if hasattr(self, '_workflow'):
                return self._workflow
            else:
                self._workflow = cls(self)
            return self._workflow
        if hasattr(docclass, 'workflow'):
            raise WorkflowException(
                "This document class already has workflow.")
        docclass.workflow = workflow

    @classmethod
    def sort_documents(cls, documents):
        """
        Sort the given collection of documents by workflow state.
        Returns a dictionary of lists.
        """
        result = {}
        for state in cls.states():
            result[state.name] = []
        for doc in documents:
            state = cls._state_values[cls._getStateValueInner(doc)]
            result[state.name].append(doc)
        return result
