(function() {

  function ol(e) {
    window.removeEventListener("DOMContentLoaded", ol, false);
    fuzzOnload();
  }

  window.addEventListener("DOMContentLoaded", ol, false);

})();
