#!/usr/bin/env python

import os


def linkJS(target_fn, file_list_fn, source_base, prologue="", module_dirs=[]):
    with open(target_fn, "wb") as target:
        target.write(prologue)

        # Add files listed in file_list_fn
        with open(file_list_fn) as file_list:
            for source_fn in file_list:
                source_fn = source_fn.replace("/", os.path.sep).strip()
                if len(source_fn) > 0 and source_fn[0] != "#":
                    addContents(source_base, source_fn, target)

        # Add all *.js files in module_dirs
        for module_base in module_dirs:
            for module_fn in os.listdir(module_base):
                if module_fn.endswith(".js"):
                    addContents(module_base, module_fn, target)


def addContents(source_base, source_fn, target):
    target.write("\n\n// " + source_fn + "\n\n")
    with open(os.path.join(source_base, source_fn)) as source:
        for line in source:
            target.write(line)
