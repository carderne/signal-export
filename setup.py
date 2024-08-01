# -*- coding: ISO-8859-1 -*-
# setup.py: the distutils script
#
# Copyright (C) 2015 David Riggleman <davidriggleman@gmail.com>
# Copyright (C) 2013 Kali Kaneko <kali@futeisha.org> (sqlcipher support)
# Copyright (C) 2005-2010 Gerhard Häring <gh@ghaering.de>
#
# This file is part of pysqlcipher.
#
# This software is provided 'as-is', without any express or implied
# warranty.  In no event will the authors be held liable for any damages
# arising from the use of this software.
#
# Permission is granted to anyone to use this software for any purpose,
# including commercial applications, and to alter it and redistribute it
# freely, subject to the following restrictions:
#
# 1. The origin of this software must not be misrepresented; you must not
# claim that you wrote the original software. If you use this software
#    in a product, an acknowledgment in the product documentation would be
#    appreciated but is not required.
# 2. Altered source versions must be plainly marked as such, and must not be
#    misrepresented as being the original software.
# 3. This notice may not be removed or altered from any source distribution.
import os
import sys
from pathlib import Path
from typing import Optional

import setuptools
from setuptools import Extension
from setuptools.command.build_ext import build_ext

# Work around clang raising hard error for unused arguments
if sys.platform == "darwin":
    os.environ["CFLAGS"] = "-Qunused-arguments"
    print("CFLAGS: " + os.environ["CFLAGS"])


def quote_argument(arg: str) -> str:
    quote = '"' if sys.platform != "win32" else '\\"'
    return quote + arg + quote


PACKAGE_NAME = "pysqlcipher3"
sources = [str(p) for p in Path("src/pysqlcipher3/c").glob("*.c")]
EXTENSION_MODULE_NAME = "._sqlite3"
define_macros: Optional[list[tuple[str, Optional[str]]]] = [
    ("MODULE_NAME", quote_argument(PACKAGE_NAME + ".dbapi2"))
]


class AmalgationLibSQLCipherBuilder(build_ext):
    def build_extension(self, ext):  # noqa  # type: ignore
        sqlcipher_root = Path("sqlcipher")
        sqlcipher_header = sqlcipher_root /  "sqlite3.h"
        sqlcipher_source = sqlcipher_root / "sqlite3.c"
        if not sqlcipher_header.exists() or not sqlcipher_source.exists():
            raise RuntimeError("SQLCipher amalgamation not found")

        ext.include_dirs.append(str(sqlcipher_root))
        ext.sources.append(str(sqlcipher_source))

        # build with fulltext search enabled
        ext.define_macros.append(("SQLITE_ENABLE_FTS3", "1"))
        ext.define_macros.append(("SQLITE_ENABLE_RTREE", "1"))

        # SQLCipher options
        ext.define_macros.append(("SQLITE_ENABLE_LOAD_EXTENSION", "1"))
        ext.define_macros.append(("SQLITE_HAS_CODEC", "1"))
        ext.define_macros.append(("SQLITE_TEMP_STORE", "2"))

        if sys.platform == "win32":
            # Try to locate openssl
            openssl_conf = os.environ.get("OPENSSL_CONF")
            if not openssl_conf:
                error_message = "Fatal error: OpenSSL could not be detected!"
                raise RuntimeError(error_message)

            openssl = os.path.dirname(os.path.dirname(openssl_conf))
            openssl_lib_path = os.path.join(openssl, "lib")

            # Configure the compiler
            ext.include_dirs.append(os.path.join(openssl, "include"))
            ext.define_macros.append(("inline", "__inline"))

            # Configure the linker
            ext.extra_link_args.append("libeay32.lib")
            ext.extra_link_args.append("/LIBPATH:" + openssl_lib_path)
        else:
            ext.extra_link_args.append("-lcrypto")

        build_ext.build_extension(self, ext)


setuptools.setup(
    ext_modules=[
        Extension(
            name=PACKAGE_NAME + EXTENSION_MODULE_NAME,
            sources=sources,
            define_macros=define_macros,
        )
    ],
    cmdclass={"build_ext": AmalgationLibSQLCipherBuilder},
)
