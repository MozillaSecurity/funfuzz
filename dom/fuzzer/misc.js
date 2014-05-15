function aC(r, n) { if (r) { r.appendChild(n); } else { dumpln("aC->rM"); rM(n); } }
function iB(r, n) { if (r) { r.parentNode.insertBefore(n, r); } else { dumpln("iB->rM"); rM(n); } }
function rM(n)    { n.parentNode.removeChild(n); }


function getKeysFromHash(h)
{
  var a = [];
  for (var p in h)
    a.push(p);
  return a;
}

function isPrimitive(v)
{
// NB: document.all is == but not ===
// NB: typeof== is optimized by spidermonkey
return (v === null || v === undefined || typeof v == "boolean" || typeof v == "number" || typeof v == "string");
}


/*

function insertAsFirstChild(p, n)
{
  p.insertBefore(n, p.firstChild);
}

function removeChildAt(p, i)
{
  var n = p.childNodes[i];

  p.removeChild(n);
}
*/
