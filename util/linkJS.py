#!/usr/bin/env python

import os

def linkJS(target_fn, file_list_fn, source_base):
    with open(target_fn, "w") as target:
        with open(file_list_fn) as file_list:
            for source_fn in file_list:
                source_fn = source_fn.strip()
                if len(source_fn) > 0 and source_fn[0] != "#":
                    target.write("\n\n\n// " + source_fn + "\n\n")
                    source_fn = source_fn.replace("/", os.path.sep)
                    with open(os.path.join(source_base, source_fn)) as source:
                        for line in source:
                            target.write(line)
