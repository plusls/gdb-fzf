import ctypes
from typing import List
import subprocess

class HIST_ENTRY(ctypes.Structure):
    _fields_ = [
        ('line', ctypes.c_char_p),
        ('timestamp', ctypes.c_char_p),
        ('data', ctypes.c_void_p),
    ]


def get_libreadline() -> ctypes.CDLL:
    libreadline = ctypes.CDLL('libreadline.so.8')
    # HIST_ENTRY** history_list()
    libreadline.history_list.restype = ctypes.POINTER(ctypes.POINTER(HIST_ENTRY))

    # int rl_generic_bind (const char *keyseq, rl_command_func_t *function)
    libreadline.rl_bind_keyseq.argtypes = (ctypes.c_char_p, ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_int, ctypes.c_int))
    libreadline.rl_bind_keyseq.restype = ctypes.c_int

    # void rl_add_undo (enum undo_code, int, int, char * text);
    # enum undo_code { UNDO_DELETE, UNDO_INSERT, UNDO_BEGIN, UNDO_END };
    libreadline.rl_add_undo.argtypes = (ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_char_p)

    # int rl_delete_text (int from, int to)
    libreadline.rl_delete_text.argtypes = (ctypes.c_int, ctypes.c_int)
    libreadline.rl_delete_text.restype = ctypes.c_int

    # int rl_insert_text (const char *string)
    libreadline.rl_insert_text.argtypes = (ctypes.c_char_p, )
    libreadline.rl_insert_text.restype = ctypes.c_int

    # int rl_forced_update_display
    libreadline.rl_forced_update_display.restype = ctypes.c_int

    # int rl_crlf
    libreadline.rl_crlf.restype = ctypes.c_int

    return libreadline

@ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_int, ctypes.c_int)
def fzf_search_history (sign: int, key: int) -> int:
    libreadline = get_libreadline()
    history = get_history(libreadline)
    libreadline.rl_crlf()
    rl_line_buffer_ptr = ctypes.c_char_p.in_dll(libreadline , "rl_line_buffer")
    query = ctypes.string_at(rl_line_buffer_ptr).decode()
    make_readline_line(libreadline, get_fzf_result(query, history))
    libreadline.rl_forced_update_display()
    return 0

def make_readline_line(libreadline: ctypes.CDLL, s: bytes):
    rl_line_buffer_ptr = ctypes.c_char_p.in_dll(libreadline , "rl_line_buffer")
    rl_line_buffer = ctypes.string_at(rl_line_buffer_ptr)
    rl_point_ptr = ctypes.c_int.in_dll(libreadline , "rl_point")
    rl_end_ptr = ctypes.c_int.in_dll(libreadline , "rl_end")
    rl_mark_ptr = ctypes.c_int.in_dll(libreadline , "rl_mark")

    if s != rl_line_buffer:
        libreadline.rl_add_undo(2, 0, 0, None)
        libreadline.rl_delete_text(0, rl_point_ptr.value)
        rl_point_ptr.value = 0
        rl_end_ptr.value = 0
        rl_mark_ptr.value = 0
        libreadline.rl_insert_text(s)
        libreadline.rl_add_undo(3, 0, 0, None)



def get_history(libreadline: ctypes.CDLL) -> List[bytes]:
    hlist = libreadline.history_list()
    ret: List[bytes] = []
    if not hlist:
        return ret
    i = 0
    while True:
        hentry = hlist[i]
        if not hentry:
            break
        ret.append(hentry[0].line)
        i += 1
    return ret

def get_fzf_result(query: str, history_list: List[bytes]) -> bytes:
    args = ['fzf',
            '--print0',
            '--read0',
            '--no-multi',
            '--height=40%',
            '--layout=reverse',
            # '--tac', os.environ.get('GDB_FZF_OPTS', ''),
            '--query', query
            ]
    p = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    assert(p.stdin)
    assert(p.stdout)
    for history in history_list:
        p.stdin.write(history + b'\x00')
    p.stdin.flush()
    res = p.stdout.read()
    p.wait()
    return res

def patch():
    libreadline = get_libreadline()
    assert(libreadline.rl_bind_keyseq(b"\\C-r", fzf_search_history) == 0)


patch()
