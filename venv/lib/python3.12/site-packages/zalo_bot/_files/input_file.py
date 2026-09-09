"""This module contains an object that represents a Zalo Bot InputFile."""

import mimetypes
from typing import IO, Optional, Union
from uuid import uuid4

from zalo_bot._utils.files import guess_file_name, load_file
from zalo_bot._utils.strings import TextEncoding
from zalo_bot._utils.types import FieldTuple

_DEFAULT_MIME_TYPE = "application/octet-stream"


class InputFile:
    """This object represents a Zalo Bot InputFile.

    .. versionchanged:: 20.0

        * The former attribute ``attach`` was renamed to :attr:`attach_name`.
        * Method ``is_image`` was removed. If you pass :obj:`bytes` to :paramref:`obj` and would
          like to have the mime type automatically guessed, please pass :paramref:`filename`
          in addition.

    Args:
        obj (:term:`file object` | :obj:`bytes` | :obj:`str`): An open file descriptor or the files
            content as bytes or string.

            Note:
                If :paramref:`obj` is a string, it will be encoded as bytes via
                :external:obj:`obj.encode('utf-8') <str.encode>`.

        filename (:obj:`str`, optional): Filename for this InputFile.
        attach (:obj:`bool`, optional): Pass :obj:`True` if the parameter this file belongs to in
            the request to Zalo Bot should point to the multipart data via an ``attach://`` URI.
            Defaults to `False`.
        read_file_handle (:obj:`bool`, optional): If :obj:`True` and :paramref:`obj` is a file
            handle, the data will be read from the file handle on initialization of this object.
            If :obj:`False`, the file handle will be passed on to the
            `networking backend <zalo_bot.request.BaseRequest.do_request>`_ which will have to
            handle the reading. Defaults to :obj:`True`.

            Tip:
                If you upload extremely large files, you may want to set this to :obj:`False` to
                avoid reading the complete file into memory. Additionally, this may be supported
                better by the networking backend (in particular it is handled better by
                the default :class:`~zalo_bot.request.HTTPXRequest`).

            Important:
                If you set this to :obj:`False`, you have to ensure that the file handle is still
                open when the request is made. In particular, the following snippet can *not* work
                as expected.

                .. code-block:: python

                    with open('file.txt', 'rb') as file:
                        input_file = InputFile(file, read_file_handle=False)

                    # here the file handle is already closed and the upload will fail
                    await bot.send_document(chat_id, input_file)


    Attributes:
        input_file_content (:obj:`bytes` | :class:`IO`): The binary content of the file to send.
        attach_name (:obj:`str`): Optional. If present, the parameter this file belongs to in
            the request to Zalo Bot should point to the multipart data via a an URI of the form
            ``attach://<attach_name>`` URI.
        filename (:obj:`str`): Filename for the file to be sent.
        mimetype (:obj:`str`): The mimetype inferred from the file to be sent.

    """

    __slots__ = ("attach_name", "filename", "input_file_content", "mimetype")

    def __init__(
        self,
        obj: Union[IO[bytes], bytes, str],
        filename: Optional[str] = None,
        attach: bool = False,
        read_file_handle: bool = True,
    ):
        if isinstance(obj, bytes):
            self.input_file_content: Union[bytes, IO[bytes]] = obj
        elif isinstance(obj, str):
            self.input_file_content = obj.encode(TextEncoding.UTF_8)
        elif read_file_handle:
            reported_filename, self.input_file_content = load_file(obj)
            filename = filename or reported_filename
        else:
            self.input_file_content = obj
            filename = filename or guess_file_name(obj)

        self.attach_name: Optional[str] = "attached" + uuid4().hex if attach else None

        if filename:
            self.mimetype: str = (
                mimetypes.guess_type(filename, strict=False)[0] or _DEFAULT_MIME_TYPE
            )
        else:
            self.mimetype = _DEFAULT_MIME_TYPE

        self.filename: str = filename or self.mimetype.replace("/", ".")

    @property
    def field_tuple(self) -> FieldTuple:
        """Field tuple representing the contents of the file for upload to the Zalo Bot servers.

        Returns:
            Tuple[:obj:`str`, :obj:`bytes` | :class:`IO`, :obj:`str`]:
        """
        return self.filename, self.input_file_content, self.mimetype

    @property
    def attach_uri(self) -> Optional[str]:
        """URI to insert into the JSON data for uploading the file. Returns :obj:`None`, if
        :attr:`attach_name` is :obj:`None`.
        """
        return f"attach://{self.attach_name}" if self.attach_name else None
