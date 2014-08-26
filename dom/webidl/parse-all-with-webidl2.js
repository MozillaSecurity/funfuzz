// Run this in a SpiderMonkey shell (not Node)

// Where to find WebIDL files (pre-processed and normal)
const BUILD = "/Users/jruderman/builds/mozilla-central-debug/";
const TREE = "/Users/jruderman/trees/mozilla-central/";

// Load a library that parses WebIDL files into a JSON-like format
// (https://github.com/darobin/webidl2.js + my patch "mozilla-ize-webidl2.diff")
var window = {};
load("/Users/jruderman/code/webidl2.js/lib/webidl2.js");

function assert(p) { if (!p) throw "Assertion failed"; }
function last(a) { return a[a.length - 1]; }

function parseAll()
{
    var generated = {};
    var idlTrees = [];

    // First, read the generated and preprocessed WebIDL files
    // https://mxr.mozilla.org/mozilla-central/source/dom/webidl/moz.build#12
    system("ls " + BUILD + "dom/bindings/*.webidl > /Users/jruderman/Desktop/webidl-generated.list");
    var list = snarf("/Users/jruderman/Desktop/webidl-generated.list").split("\n");
    for (let fn of list) {
        if (!fn)
            continue;
        leaf = last(fn.split("/"));
        if (leaf.startsWith("Test")) {
            continue;
        }
        generated[leaf] = true;
        idlTrees.push(parse(fn));
    }

    // Second, read the normal WebIDL files (skipping the ones that are really input for preprocessing)
    system("ls " + TREE + "dom/webidl/*.webidl > /Users/jruderman/Desktop/webidl-tree.list");
    list = snarf("/Users/jruderman/Desktop/webidl-tree.list").split("\n");
    for (let fn of list) {
        if (!fn) {
            continue;
        }
        leaf = last(fn.split("/"));
        if (generated[leaf]) {
            continue;
        }
        idlTrees.push(parse(fn));
    }

    return idlTrees;
}

function parse(fullFn)
{
    var idlText = snarf(fullFn);
    idlText = idlText.replace(/interface \w*;/g, ""); // remove declarations of external interfaces (a mozilla extension)
    idlText = idlText.replace(/jsonifier;/g, ""); // remove another mozilla extension

    try {
        return window.WebIDL2.parse(idlText);
    } catch(e) {
        print("Error in: " + fullFn);
        linematch = /line (\d+)/.exec(e);
        if (linematch) {
            linenum = parseInt(linematch[1]);
            print(idlText.split(/\n/)[linenum - 1]);
        }
        print(e);
        return null;
    }
}

// * Rearranges items to be dict-by-name instead of by file and sequence within file
// * Combines multiple items that refer to the same interface (partials + implements)
function flattenIDL(idlTrees)
{
    var items = {};

    // Gather (non-partial) interfaces, along with {dictionaries, enums, callbacks, callback interfaces, typedefs}
    for (let fileTree of idlTrees) {
        for (let item of fileTree) {
            if ("name" in item && !item.partial) {
                assert(!(item.name in items));
                if (item.name in items) {
                    items[item.name] = zipPartial(items[item.name], item);
                } else {
                    items[item.name] = item;
                }
            }
            if (!("name" in item) && item.type != "implements") {
                print("I don't know where to put this! " + item.type);
            }
        }
    }

    // Gather updates to interfaces {"implements" statements, partial interfaces}
    for (let fileTree of idlTrees) {
        for (let item of fileTree) {
            if (item.type == "implements") {
                let target = items[item.target];
                if (!("implements" in target)) {
                    target.implements = [];
                }
                target.implements.push(item.implements);
            }
            if (item.partial) {
                items[item.name].members = items[item.name].members.concat(item.members);
            }
        }
    }

    return items;
}

function main(fn)
{
    var trees;
    if (fn) {
        trees = [parse(fn)];
    } else {
        trees = parseAll();
    }

    print(JSON.stringify(flattenIDL(trees), null, 4));
}

main(scriptArgs[0]);
