"""Base class for Zalo Objects."""
import contextlib
import datetime
import inspect
import json
from collections.abc import Sized
from contextlib import contextmanager
from copy import deepcopy
from itertools import chain
from types import MappingProxyType
from typing import (
    TYPE_CHECKING,
    Any,
    ClassVar,
    Dict,
    Iterator,
    List,
    Mapping,
    Optional,
    Set,
    Tuple,
    Type,
    TypeVar,
    Union,
    cast,
)

from zalo_bot._utils.datetime import to_timestamp
from zalo_bot._utils.default_value import DefaultValue
from zalo_bot._utils.types import JSONDict
from zalo_bot._utils.warnings import warn

if TYPE_CHECKING:
    from zalo_bot import Bot

Zalo_co = TypeVar("Zalo_co", bound="ZaloObject", covariant=True)


class ZaloObject:
    """Base class for most Zalo Bot objects.

    Objects of this type are subscriptable with strings. See :meth:`__getitem__` for more details.
    The :mod:`pickle` and :func:`~copy.deepcopy` behavior of objects of this type are defined by
    :meth:`__getstate__`, :meth:`__setstate__` and :meth:`__deepcopy__`.

    Tip:
        Objects of this type can be serialized via Python's :mod:`pickle` module and pickled
        objects from one version of PTB are usually loadable in future versions. However, we can
        not guarantee that this compatibility will always be provided. At least a manual one-time
        conversion of the data may be needed on major updates of the library.

        * Removed argument and attribute ``bot`` for several subclasses. Use
          :meth:`set_bot` and :meth:`get_bot` instead.
        * Removed the possibility to pass arbitrary keyword arguments for several subclasses.
        * String representations objects of this type was overhauled. See :meth:`__repr__` for
          details. As this class doesn't implement :meth:`object.__str__`, the default
          implementation will be used, which is equivalent to :meth:`__repr__`.
        * Objects of this class (or subclasses) are now immutable. This means that you can't set
          or delete attributes anymore. Moreover, attributes that were formerly of type
          :obj:`list` are now of type :obj:`tuple`.

    Arguments:
        api_kwargs (Dict[:obj:`str`, any], optional): |toapikwargsarg|

    Attributes:
        api_kwargs (:obj:`types.MappingProxyType` [:obj:`str`, any]): |toapikwargsattr|

            .. versionadded:: 20.0

    """

    __slots__ = ("_bot", "_frozen", "_id_attrs", "api_kwargs")

    # Cache parameter names of __init__ method
    __INIT_PARAMS: ClassVar[Set[str]] = set()
    # Check if __INIT_PARAMS has been set for current class
    __INIT_PARAMS_CHECK: Optional[Type["ZaloObject"]] = None

    def __init__(self, *, api_kwargs: Optional[JSONDict] = None) -> None:
        # Classes without arguments still need to implement __init__
        self._frozen: bool = False
        self._id_attrs: Tuple[object, ...] = ()
        self._bot: Optional[Bot] = None
        # See docstring of _apply_api_kwargs for api_kwargs handling
        self.api_kwargs: Mapping[str, Any] = MappingProxyType(api_kwargs or {})

    def __eq__(self, other: object) -> bool:
        """Compares this object with :paramref:`other` in terms of equality.
        If this object and :paramref:`other` are `not` objects of the same class,
        this comparison will fall back to Python's default implementation of :meth:`object.__eq__`.
        Otherwise, both objects may be compared in terms of equality, if the corresponding
        subclass of :class:`ZaloObject` has defined a set of attributes to compare and
        the objects are considered to be equal, if all of these attributes are equal.
        If the subclass has not defined a set of attributes to compare, a warning will be issued.

        Tip:
            If instances of a class in the :mod:`zalo_bot` module are comparable in terms of
            equality, the documentation of the class will state the attributes that will be used
            for this comparison.

        Args:
            other (:obj:`object`): The object to compare with.

        Returns:
            :obj:`bool`

        """
        if isinstance(other, self.__class__):
            print(1231231, self._id_attrs, other._id_attrs)
            if not self._id_attrs:
                warn(
                    f"Objects of type {self.__class__.__name__} can not be meaningfully tested for"
                    " equivalence.",
                    stacklevel=2,
                )
            if not other._id_attrs:
                warn(
                    f"Objects of type {other.__class__.__name__} can not be meaningfully tested"
                    " for equivalence.",
                    stacklevel=2,
                )
            print(1231231, self._id_attrs, other._id_attrs)
            return self._id_attrs == other._id_attrs
        return super().__eq__(other)

    def __hash__(self) -> int:
        """Builds a hash value for this object such that the hash of two objects is equal if and
        only if the objects are equal in terms of :meth:`__eq__`.

        Returns:
            :obj:`int`
        """
        if self._id_attrs:
            return hash((self.__class__, self._id_attrs))
        return super().__hash__()

    def __setattr__(self, key: str, value: object) -> None:
        """Overrides :meth:`object.__setattr__` to prevent the overriding of attributes.

        Raises:
            :exc:`AttributeError`
        """
        # Protected attributes can always be set for internal use
        if key[0] == "_" or not getattr(self, "_frozen", True):
            super().__setattr__(key, value)
            return

        raise AttributeError(
            f"Attribute `{key}` of class `{self.__class__.__name__}` can't be set!"
        )

    def __delattr__(self, key: str) -> None:
        """Overrides :meth:`object.__delattr__` to prevent the deletion of attributes.

        Raises:
            :exc:`AttributeError`
        """
        # Protected attributes can always be set for internal use
        if key[0] == "_" or not getattr(self, "_frozen", True):
            super().__delattr__(key)
            return

        raise AttributeError(
            f"Attribute `{key}` of class `{self.__class__.__name__}` can't be deleted!"
        )

    def __repr__(self) -> str:
        """Gives a string representation of this object in the form
        ``ClassName(attr_1=value_1, attr_2=value_2, ...)``, where attributes are omitted if they
        have the value :obj:`None` or are empty instances of :class:`collections.abc.Sized` (e.g.
        :class:`list`, :class:`dict`, :class:`set`, :class:`str`, etc.).

        As this class doesn't implement :meth:`object.__str__`, the default implementation
        will be used, which is equivalent to :meth:`__repr__`.

        Returns:
            :obj:`str`
        """
        # Unambiguous and readable representation
        as_dict = self._get_attrs(recursive=False, include_private=False)

        if not self.api_kwargs:
            # Drop api_kwargs from representation if empty
            as_dict.pop("api_kwargs", None)
        else:
            # Skip "mappingproxy" part of repr
            as_dict["api_kwargs"] = dict(self.api_kwargs)

        contents = ", ".join(
            f"{k}={as_dict[k]!r}"
            for k in sorted(as_dict.keys())
            if (
                as_dict[k] is not None
                and not (
                    isinstance(as_dict[k], Sized)
                    and len(as_dict[k]) == 0  # type: ignore[arg-type]
                )
            )
        )

        return f"{self.__class__.__name__}({contents})"

    def __getitem__(self, item: str) -> object:
        """
        Objects of this type are subscriptable with strings, where
        ``zalo_object["attribute_name"]`` is equivalent to ``zalo_object.attribute_name``.

        Tip:
            This is useful for dynamic attribute lookup, i.e. ``zalo_object[arg]`` where the
            value of ``arg`` is determined at runtime.
            In all other cases, it's recommended to use the dot notation instead, i.e.
            ``zalo_object.attribute_name``.

            ``zalo_object['from']`` will look up the key ``from_user``. This is to account for
            special cases like :attr:`Message.from_user` that deviate from the official Bot API.

        Args:
            item (:obj:`str`): The name of the attribute to look up.

        Returns:
            :obj:`object`

        Raises:
            :exc:`KeyError`: If the object does not have an attribute with the appropriate name.
        """
        if item == "from":
            item = "from_user"
        try:
            return getattr(self, item)
        except AttributeError as exc:
            raise KeyError(
                f"Objects of type {self.__class__.__name__} don't have an attribute called "
                f"`{item}`."
            ) from exc

    def __getstate__(self) -> Dict[str, Union[str, object]]:
        """Customize the behavior of :mod:`pickle`.

        Returns:
            :obj:`dict`
        """
        # MappingProxyType is not pickable, convert to dict
        state = self._get_attrs(include_private=True, recursive=False, remove_bot=True, convert_default_vault=False)
        state["api_kwargs"] = dict(self.api_kwargs)
        return state

    def __setstate__(self, state: Dict[str, object]) -> None:
        """Customize the behavior of :mod:`pickle`.

        Args:
            state (:obj:`dict`): The state dictionary.
        """
        self._unfreeze()

        # Make sure that we have a `_bot` attribute. This is necessary, since __getstate__ omits
        # this as Bots are not pickable.
        self._bot = None

        # get api_kwargs first because we may need to add entries to it (see try-except below)
        api_kwargs = cast(Dict[str, object], state.pop("api_kwargs", {}))
        # get _frozen before the loop to avoid setting it to True in the loop
        frozen = state.pop("_frozen", False)

        for key, val in state.items():
            try:
                setattr(self, key, val)
            except AttributeError:
                # So an attribute was deprecated and removed from the class. Let's handle this:
                # 1) Is the attribute now a property with no setter? Let's check that:
                if isinstance(getattr(self.__class__, key, None), property):
                    # It is, so let's try to set the "private attribute" instead
                    try:
                        setattr(self, f"_{key}", val)
                    # If this fails as well, guess we've completely removed it. Let's add it to
                    # api_kwargs as fallback
                    except AttributeError:
                        api_kwargs[key] = val

                # 2) The attribute is a private attribute, i.e. it went through case 1) in the past
                elif key.startswith("_"):
                    continue  # skip adding this to api_kwargs, the attribute is lost forever.
                api_kwargs[key] = val  # add it to api_kwargs as fallback

        # For api_kwargs we first apply any kwargs that are already attributes of the object
        # and then set the rest as MappingProxyType attribute. Converting to MappingProxyType
        # is necessary, since __getstate__ converts it to a dict as MPT is not pickable.
        self._apply_api_kwargs(api_kwargs)
        self.api_kwargs = MappingProxyType(api_kwargs)
        # Apply freezing if necessary
        # we .get(…) the setting for backwards compatibility with objects that were pickled
        # before the freeze feature was introduced
        if frozen:
            self._freeze()

    def __deepcopy__(self: Zalo_co, memodict: Dict[int, object]) -> Zalo_co:
        """Customize the behavior of :func:`copy.deepcopy`.

        Args:
            memodict (:obj:`dict`): The memo dictionary.

        Returns:
            :obj:`ZaloObject`
        """
        bot = self._bot  # Save bot so we can set it after copying
        self.set_bot(None)  # set to None so it is not deepcopied
        cls = self.__class__
        result = cls.__new__(cls)  # create a new instance
        memodict[id(self)] = result  # save the id of the object in the dict

        result._frozen = False  # Unfreeze new object for setting attributes

        # now we set the attributes in the deepcopied object
        for k in self._get_attrs_names(include_private=True):
            if k == "_frozen":
                # Setting the frozen status to True would prevent the attributes from being set
                continue
            if k == "api_kwargs":
                # Need to copy api_kwargs manually, since it's a MappingProxyType is not
                # pickable and deepcopy uses the pickle interface
                setattr(result, k, MappingProxyType(deepcopy(dict(self.api_kwargs), memodict)))
                continue

            try:
                setattr(result, k, deepcopy(getattr(self, k), memodict))
            except AttributeError:
                # Skip missing attributes. This can happen if the object was loaded from a pickle
                # file that was created with an older version of the library, where the class
                # did not have the attribute yet.
                continue

        # Apply freezing if necessary
        if self._frozen:
            result._freeze()

        result.set_bot(bot)  # Assign the bots back
        self.set_bot(bot)
        return result

    @staticmethod
    def _parse_data(data: Optional[JSONDict]) -> Optional[JSONDict]:
        """Should be called by subclasses that override de_json to ensure that the input
        is not altered. Whoever calls de_json might still want to use the original input
        for something else.
        """
        return None if data is None else data.copy()

    @classmethod
    def _de_json(
        cls: Type[Zalo_co],
        data: Optional[JSONDict],
        bot: Optional["Bot"],
        api_kwargs: Optional[JSONDict] = None,
    ) -> Optional[Zalo_co]:
        if data is None:
            return None

        # try-except is significantly faster in case we already have a correct argument set
        try:
            obj = cls(**data, api_kwargs=api_kwargs)
        except TypeError as exc:
            if "__init__() got an unexpected keyword argument" not in str(exc):
                raise

            if cls.__INIT_PARAMS_CHECK is not cls:
                signature = inspect.signature(cls)
                cls.__INIT_PARAMS = set(signature.parameters.keys())
                cls.__INIT_PARAMS_CHECK = cls

            api_kwargs = api_kwargs or {}
            existing_kwargs: JSONDict = {}
            for key, value in data.items():
                (existing_kwargs if key in cls.__INIT_PARAMS else api_kwargs)[key] = value

            obj = cls(api_kwargs=api_kwargs, **existing_kwargs)

        obj.set_bot(bot=bot)
        return obj

    @classmethod
    def de_json(
        cls: Type[Zalo_co], data: Optional[JSONDict], bot: Optional["Bot"] = None
    ) -> Optional[Zalo_co]:
        """Converts JSON data to a Zalo object.

        Args:
            data (Dict[:obj:`str`, ...]): The JSON data.
            bot (:class:`zalo_bot.Bot`, optional): The bot associated with this object. Defaults to
                :obj:`None`, in which case shortcut methods will not be available.


                :paramref:`bot` is now optional and defaults to :obj:`None`

        Returns:
            The Zalo object.

        """
        return cls._de_json(data=data, bot=bot)

    @classmethod
    def de_list(
        cls: Type[Zalo_co], data: Optional[List[JSONDict]], bot: Optional["Bot"] = None
    ) -> Tuple[Zalo_co, ...]:
        """Converts a list of JSON objects to a tuple of Zalo objects.

           * Returns a tuple instead of a list.
           * Filters out any :obj:`None` values.

        Args:
            data (List[Dict[:obj:`str`, ...]]): The JSON data.
            bot (:class:`zalo_bot.Bot`, optional): The bot associated with these object. Defaults
                to :obj:`None`, in which case shortcut methods will not be available.

                :paramref:`bot` is now optional and defaults to :obj:`None`

        Returns:
            A tuple of Zalo objects.

        """
        if not data:
            return ()

        return tuple(obj for obj in (cls.de_json(d, bot) for d in data) if obj is not None)

    @contextmanager
    def _unfrozen(self: Zalo_co) -> Iterator[Zalo_co]:
        """Context manager to temporarily unfreeze the object. For internal use only.

        Note:
            with to._unfrozen() as other_to:
                assert to is other_to
        """
        self._unfreeze()
        yield self
        self._freeze()

    def _freeze(self) -> None:
        self._frozen = True

    def _unfreeze(self) -> None:
        self._frozen = False

    def _apply_api_kwargs(self, api_kwargs: JSONDict) -> None:
        """Move values from api_kwargs to object attributes where appropriate.
        *Edits `api_kwargs` in place!*

        Currently only called during unpickling process.
        """
        # Convert to list to ensure length doesn't change during iteration
        for key in list(api_kwargs.keys()):
            # Property attributes are not settable, set private attribute instead
            if isinstance(getattr(self.__class__, key, None), property):
                # If setattr fails, leave value in api_kwargs
                with contextlib.suppress(AttributeError):
                    setattr(self, f"_{key}", api_kwargs.pop(key))
            elif getattr(self, key, True) is None:
                setattr(self, key, api_kwargs.pop(key))

    def _get_attrs_names(self, include_private: bool) -> Iterator[str]:
        """Get attribute names for serialization.

        Args:
            include_private (:obj:`bool`): Whether to include private attributes.

        Returns:
            Iterator[:obj:`str`]: Attribute names.
        """
        # Get all attributes from MRO, excluding object class
        all_slots = (s for c in self.__class__.__mro__[:-1] for s in c.__slots__)  # type: ignore
        # Chain class slots with user-defined subclass __dict__
        all_attrs = (
            chain(all_slots, self.__dict__.keys()) if hasattr(self, "__dict__") else all_slots
        )

        if include_private:
            return all_attrs
        return (attr for attr in all_attrs if not attr.startswith("_"))

    def _get_attrs(
        self,
        include_private: bool = False,
        recursive: bool = False,
        remove_bot: bool = False,
        convert_default_vault: bool = True,
    ) -> Dict[str, Union[str, object]]:
        """Get object attributes.

        Args:
            include_private (:obj:`bool`): Whether to include private variables.
            recursive (:obj:`bool`): Convert ZaloObjects to dictionaries if True.
            remove_bot (:obj:`bool`): Whether to include bot in result.
            convert_default_vault (:obj:`bool`): Convert DefaultValue to true value.

        Returns:
            :obj:`dict`: Attribute names and values.
        """
        data = {}

        for key in self._get_attrs_names(include_private=include_private):
            value = (
                DefaultValue.get_value(getattr(self, key, None))
                if convert_default_vault
                else getattr(self, key, None)
            )

            if value is not None:
                if recursive and hasattr(value, "to_dict"):
                    data[key] = value.to_dict(recursive=True)
                else:
                    data[key] = value
            elif not recursive:
                data[key] = value

        if recursive and data.get("from_user"):
            data["from"] = data.pop("from_user", None)
        if remove_bot:
            data.pop("_bot", None)
        return data

    def to_json(self) -> str:
        """Gives a JSON representation of object.

        Returns:
            :obj:`str`
        """
        return json.dumps(self.to_dict())

    def to_dict(self, recursive: bool = True) -> JSONDict:
        """Get object as dictionary.

        Args:
            recursive (:obj:`bool`, optional): Convert ZaloObjects to dictionaries.
                Defaults to :obj:`True`.

        Returns:
            :obj:`dict`
        """
        out = self._get_attrs(recursive=recursive)

        # Convert TGObjects to dicts in sequences and datetimes to timestamps
        pop_keys: Set[str] = set()
        for key, value in out.items():
            if isinstance(value, (tuple, list)):
                if not value:
                    # Not popping directly to avoid changing dict size during iteration
                    pop_keys.add(key)
                    continue

                val = []  # Empty list for converted values
                for item in value:
                    if hasattr(item, "to_dict"):
                        val.append(item.to_dict(recursive=recursive))
                    # Handle nested tuples/lists
                    elif isinstance(item, (tuple, list)):
                        val.append(
                            [
                                i.to_dict(recursive=recursive) if hasattr(i, "to_dict") else i
                                for i in item
                            ]
                        )
                    else:  # Non-TGObject, append as-is
                        val.append(item)
                out[key] = val

            elif isinstance(value, datetime.datetime):
                out[key] = to_timestamp(value)

        for key in pop_keys:
            out.pop(key)

        # Effectively "unpack" api_kwargs into `out`:
        out.update(out.pop("api_kwargs", {}))  # type: ignore[call-overload]
        return out

    def get_bot(self) -> "Bot":
        """Returns the :class:`zalo_bot.Bot` instance associated with this object.

        .. seealso:: :meth:`set_bot`

        .. versionadded: 20.0

        Raises:
            RuntimeError: If no :class:`zalo_bot.Bot` instance was set for this object.
        """
        if self._bot is None:
            raise RuntimeError(
                "This object has no bot associated with it. Shortcuts cannot be used."
            )
        return self._bot

    def set_bot(self, bot: Optional["Bot"]) -> None:
        """Sets the :class:`zalo_bot.Bot` instance associated with this object.

        .. seealso:: :meth:`get_bot`

        Arguments:
            bot (:class:`zalo_bot.Bot` | :obj:`None`): The bot instance.
        """
        self._bot = bot
