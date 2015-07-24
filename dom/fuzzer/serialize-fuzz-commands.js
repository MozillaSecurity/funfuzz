// After reducing the fuzzCommands array and removing all references to the fuzzer,
// call serializeAllFuzzCommands to turn the testcase into a nicer form for reporting bugs.

function serializeFuzzCommands()
{
    // Gather fuzzCommands, except for leading junk and trailing quitApplication, into a flatter function.
    var boomContents = serializeFuzzCommandsSegment(0, fuzzCommands.length, "    ");
    var boom = "function boom() {\n" + boomContents + "}\n";

    // Create a simple document that just runs this script.
    if (document instanceof SVGDocument) {
        dumpln(serializeToSVGDocument(boom));
    } else if (document instanceof XMLDocument) {
        dumpln(serializeToXHTMLDocument(boom));
    } else {  // document instanceof HTMLDocument, hopefully
        dumpln(serializeToHTMLDocument(boom));
    }
}

function serializeFuzzCommandsSegment(start, end, indent)
{
    var s = "";
    for (var i = start; i < end; ++i) {
        var c = fuzzCommands[i];
        if (!("note" in c) || typeof c.note == "number" || c.note == "seri") {
            if (c.fun) {
                // A function. Inline its contents. (Assume it doesn't throw, rely on having its own scope, or contain native code.)
                s += indent + functionContents(c.fun) + "\n";
            } else if (c.rest) {
                // A timeout. Grab the remainder through recursion instead of iteration, indenting them in a setTimeout block.
                var timerCallbackBlock = serializeFuzzCommandsSegment(i + 1, end, indent + "    ");
                var timeout = ("timeout" in c) ? c.timeout : (inverval != undefined) ? interval : fuzzSettings[3];
                return s + indent + "setTimeout(function() {\n" + timerCallbackBlock + indent + "}, " + timeout + ");\n";
            }
        }
    }
    return s;
}

function functionContents(f)
{
    var fs = f + "";
    var openBrace = fs.indexOf("{");
    var closeBrace = fs.lastIndexOf("}");
    return fs.substring(openBrace + 1, closeBrace).trim();

}

function serializeToHTMLDocument(boom)
{
    var scriptElement = "<script>\n\n" + boom + "\n<\/script>\n";
    var doctype = serializeDoctype();
    var doctypen = doctype ? doctype + "\n" : "";
    var html = doctypen + '<html>\n<head>\n<meta charset="UTF-8">\n' + scriptElement + '<\/head>\n<body onload="boom();"><\/body>\n<\/html>\n';
    return html;
}

function serializeToXHTMLDocument(boom)
{
    var scriptElement = "<script>\n<![CDATA[\n\n" + boom + "\n]" + "]\>\n<\/script>\n";
    var xhtml = '<html xmlns="http://www.w3.org/1999/xhtml">\n<head>\n' + scriptElement + '<\/head><body onload="boom();"><\/body>\n<\/html>\n';
    return xhtml;
}

function serializeToSVGDocument(boom)
{
    // Wait for a window "load" event to match HTML document behavior.
    // (SVG element "load" events are special and fire during parsing.)
    var script = boom + 'window.addEventListener("load", boom, false);\n';
    var scriptElement = "<script>\n<![CDATA[\n\n" + script + "\n]" + "]>\n<\/script>\n";
    var svg = '<svg xmlns="http://www.w3.org/2000/svg">\n' + scriptElement + '<\/svg>\n';
    return svg;
}
