import windows.alpc2 as alpc
import windows.com
from windows.generated_def import USHORT, DWORD, CHAR
import ctypes
import struct


class _RPC_SYNTAX_IDENTIFIER(ctypes.Structure):
    _fields_ = [
        ("SyntaxGUID", windows.com.IID),
        ("MajorVersion", USHORT),
        ("MinorVersion", USHORT),
    ]

    def __repr__(self):
        return '<RPC_SYNTAX_IDENTIFIER "{0}" ({1}, {2})>'.format(self.SyntaxGUID.to_string(), self.MajorVersion, self.MinorVersion)
RPC_SYNTAX_IDENTIFIER = _RPC_SYNTAX_IDENTIFIER

# DEFINES

REQUEST_TYPE_CALL = 0
REQUEST_TYPE_BIND = 1

KNOW_REQUEST_TYPE = {
    REQUEST_TYPE_CALL : "REQUEST_CALL",
    REQUEST_TYPE_BIND : "REQUEST_BIND",
    }


RESPONSE_TYPE_BIND_OK = 1
RESPONSE_TYPE_FAIL = 2
RESPONSE_TYPE_SUCESS = 3


KNOW_RESPONSE_TYPE = {
    RESPONSE_TYPE_FAIL : "RESPONSE_FAIL",
    RESPONSE_TYPE_SUCESS : "RESPONSE_SUCESS",
    RESPONSE_TYPE_BIND_OK: "RESPONSE_BIND_OK",
    }


KNOWN_RPC_ERROR_CODE = {
    1783 : "RPC_X_BAD_STUB_DATA",
    1717 : "RPC_S_UNKNOWN_IF",
    1728 : "RPC_S_PROTOCOL_ERROR",
    1730 : "RPC_S_UNSUPPORTED_TRANS_SYN",
    1745 : "RPC_S_PROCNUM_OUT_OF_RANGE",
}

BIND_IF_SYNTAX_NDR32 = 1
BIND_IF_SYNTAX_NDR64 = 2
BIND_IF_SYNTAX_UNKNOWN = 4

NOT_USED = 0xBAADF00D

class ALPC_RPC_BIND(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ("request_type", DWORD),
        ("UNK1", DWORD),
        ("UNK2", DWORD),
        ("target", RPC_SYNTAX_IDENTIFIER),
        ("flags", DWORD),
        ("if_nb_ndr32", USHORT),
        ("if_nb_ndr64", USHORT),
        ("if_nb_unkn", USHORT),
        ("PAD", USHORT),
        ("register_multiple_syntax", DWORD),
        ("use_flow", DWORD),
        ("UNK5", DWORD),
        ("maybe_flow_id", DWORD),
        ("UNK7", DWORD),
        ("some_context_id", DWORD),
        ("UNK9", DWORD),
    ]


class RPCClient(object):
    REQUEST_IDENTIFIER = 0x11223344
    def __init__(self, port):
        self.alpc_client = alpc.AlpcClient(port)
        self.number_of_bind_if = 0 # if -> interface
        self.if_bind_number = {}

    def bind(self, IID_str, version=(1,0)):
        IID = windows.com.IID.from_string(IID_str)
        request = self._forge_bind_request(IID, version, self.number_of_bind_if)
        response = self._send_request(request)
        # Parse reponse
        request_type = self._get_request_type(response)
        if request_type != RESPONSE_TYPE_BIND_OK:
            raise ValueError("Unexpected reponse type. Expected RESPONSE_TYPE_BIND_OK got {0}".format(KNOW_RESPONSE_TYPE.get(request_type, request_type)))
        iid_hash = hash(buffer(IID)[:]) # TODO: add __hash__ to IID
        self.if_bind_number[iid_hash] = self.number_of_bind_if
        self.number_of_bind_if += 1
        #TODO: attach version information to IID
        return IID

    def call(self, IID, method_offset, params):
        iid_hash = hash(buffer(IID)[:])
        interface_nb = self.if_bind_number[iid_hash] # TODO: add __hash__ to IID
        request = self._forge_call_request(interface_nb, method_offset, params)
        response = self._send_request(request)
        # Parse reponse
        request_type = self._get_request_type(response)
        if request_type != RESPONSE_TYPE_SUCESS:
            raise ValueError("Unexpected reponse type. Expected RESPONSE_SUCESS got {0}".format(KNOW_RESPONSE_TYPE.get(request_type, request_type)))

        data = struct.unpack("<6I", response[:6 * 4])
        assert data[3] == self.REQUEST_IDENTIFIER
        return response[4 * 6:] # Should be the return value (not completly verified)

    def _send_request(self, request):
        response = self.alpc_client.send_receive(request)
        return response.data

    def _forge_call_request(self, interface_nb, method_offset, params):
        # TODO: differents REQUEST_IDENTIFIER for each req ?
        # TODO: what is this '0' ? (1 is also accepted) (flags ?)
        request = struct.pack("<16I", REQUEST_TYPE_CALL, NOT_USED, 1, self.REQUEST_IDENTIFIER, interface_nb, method_offset, *[NOT_USED] * 10)
        request += params
        return request

    def _forge_bind_request(self, uuid, syntaxversion, requested_if_nb):
        # if syntaxversion == (1, 0):
        #     requested_if_nb = 0x10000
        version_major, version_minor = syntaxversion
        req = ALPC_RPC_BIND()
        req.request_type = REQUEST_TYPE_BIND
        req.target = RPC_SYNTAX_IDENTIFIER(uuid, *syntaxversion)
        req.flags = BIND_IF_SYNTAX_NDR32
        req.if_nb_ndr32 = requested_if_nb
        req.if_nb_ndr64 = 0
        req.if_nb_unkn = 0
        req.register_multiple_syntax = False
        req.some_context_id = 0xB00B00B
        return buffer(req)[:]

    def _get_request_type(self, response):
        "raise if request_type == RESPONSE_TYPE_FAIL"
        request_type = struct.unpack("<I", response[:4])[0]
        if request_type == RESPONSE_TYPE_FAIL:
            error_code = struct.unpack("<5I", response)[2]
            raise ValueError("RPC Response error {0} ({1})".format(error_code, KNOWN_RPC_ERROR_CODE.get(error_code, error_code)))
        return request_type

if __name__ == "__main__":
    print("YOLO")
    import windows.rpc
    UAC_UIID = "201ef99a-7fa0-444c-9399-19ba84f12a1a"
    client = windows.rpc.find_alpc_endpoint_and_connect(UAC_UIID)
    iid = client.custom_bind(UAC_UIID)
    client.custom_call(iid, 0, "")