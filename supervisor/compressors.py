"""
Compressor implementations which used on logging file rotation.
"""

import bz2
import gzip
import os

try:
    import lzma
except ImportError:
    from backports import lzma

class Compressor:
    def compress(self, src, tgt):
        """Abstract method for compression"""
        pass


class CopyCompressor(Compressor):
    """Just copy files, do not any compressions"""
    def __init__(self):
        self.suffix = ""

    def compress(self, src, tgt):
        os.rename(src, tgt)


class GzCompressor(Compressor):
    def __init__(self, compressionLevel=9):
        self.suffix = ".gz"
        self.compressionLevel = compressionLevel

    def compress(self, src, tgt):
        with open(src, "rb") as f_src:
            with gzip.open(tgt + self.suffix, "wb", compresslevel=self.compressionLevel) as f_tgt:
                f_tgt.writelines(f_src)


class Bzip2Compressor(Compressor):
    def __init__(self, compressionLevel=9):
        self.suffix = ".bz2"
        self.compressionLevel = compressionLevel

    def compress(self, src, tgt):
        with open(src, "rb") as f_src:
            with bz2.open(tgt + self.suffix, "wb", compresslevel=self.compressionLevel) as f_tgt:
                f_tgt.writelines(f_src)


class LzmaCompressor(Compressor):
    def __init__(self, compressionLevel=9):
        self.suffix = ".xz"
        self.compressionLevel = compressionLevel

    def compress(self, src, tgt):
        with open(src, "rb") as f_src:
            with lzma.open(tgt + self.suffix, "wb", preset=self.compressionLevel) as f_tgt:
                f_tgt.writelines(f_src)
