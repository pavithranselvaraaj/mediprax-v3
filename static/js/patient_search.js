document
.getElementById("search")
.addEventListener("keyup", function(){

let filter = this.value.toLowerCase()

let rows = document.querySelectorAll("#patientTable tr")

rows.forEach(row => {

let name = row.children[0].textContent.toLowerCase()

row.style.display =
name.includes(filter) ? "" : "none"

})

})