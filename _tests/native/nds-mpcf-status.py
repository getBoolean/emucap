#!/usr/bin/env python3
"""Run the native CompactFlash register handlers against ATA status expectations."""
import argparse
import os
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source', type=Path, default=root / 'adapters/desmume-nds/work/src/desmume/src/addons/slot2_mpcf.cpp')
args = parser.parse_args()
source = args.source.read_text(encoding='utf-8')
registers = source[source.index('#define CF_REG_DATA'):source.index('static const int lfnPos')]
handlers = source[source.index('static unsigned int cflash_read('):source.index('static void cflash_close(')]
fixture = r'''
#include <cassert>
#include <cstdint>
#include <cstddef>
#include <cstdio>
#include <sys/types.h>
using u8 = uint8_t;
using u16 = uint16_t;
using u32 = uint32_t;
#define CFLASHLOG(...) ((void)0)
struct EMUFILE {
    void fseek(off_t, int) { assert(false); }
    size_t fread(void*, size_t) { assert(false); return 0; }
    void fwrite(const void*, size_t) { assert(false); }
    off_t size() { assert(false); return 0; }
};
static EMUFILE* file = nullptr;
'''
checks = r'''
int main() {
    // The command address is the ATA status register on reads. Loader startup
    // polls it before sending a command; alternate status must agree.
    for (u16 status : {u16(0x58), u16(0x80), u16(0x40), u16(0x01)}) {
        cf_reg_sts = status;
        assert(cflash_read(CF_REG_CMD) == status);
        assert(cflash_read(CF_REG_STS) == status);
    }
    cflash_write(CF_REG_CMD, CF_CMD_READ);
    assert(cf_reg_cmd == CF_CMD_READ);
    assert(cflash_read(CF_REG_CMD) == 0x58);
    cflash_write(CF_REG_CMD, CF_CMD_WRITE);
    assert(cf_reg_cmd == CF_CMD_WRITE);
    assert(cflash_read(CF_REG_CMD) == cflash_read(CF_REG_STS));
    // Pico Loader checks that LBA registers retain only their low eight bits.
    cflash_write(CF_REG_LBA1, 0xaa55);
    assert(cflash_read(CF_REG_LBA1) == 0x55);
}
'''
with tempfile.TemporaryDirectory(prefix='emucap-mpcf-status-') as directory:
    path = Path(directory)
    cpp = path / 'test.cpp'
    binary = path / ('test.exe' if os.name == 'nt' else 'test')
    cpp.write_text('#include <initializer_list>\n' + fixture + registers + handlers + checks, encoding='utf-8')
    subprocess.run([os.environ.get('CXX', 'c++'), '-std=c++11', str(cpp), '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
print('Native CompactFlash command/status reads, command writes and LBA masking passed')
