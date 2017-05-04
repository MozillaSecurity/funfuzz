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

function errorToString(e)
{
  try {
    return "" + e;
  } catch (e2) {
    return "Can't toString the error!!";
  }
}

/*
 * Call Random.pick on 'things' for 'count' iterations,
 * joining the result into a string separated by 'sep'.
 *
 * If 'sort' is true, the result will be sorted prior to join.
 *
 * eg. nsep([1, 2, 3], 2, ',') could return '1,2' or '3,3' or '3,2' etc.
 * */
function nsep(things, count, sep, sort)
{
  var r = [];
  for (var i = 0; i < count; i++) {
    r.push(Random.pick(things));
  }
  if (sort) {
    r.sort();
  }
  return r.join(sep);
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
