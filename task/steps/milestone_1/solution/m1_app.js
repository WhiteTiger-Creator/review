/* Milestone 1 placeholder — replaced in milestone 3 */
console.log("notes app static shell");
var API = "/api/notes";
fetch(API).then(function (r) {
  return r.json();
});
