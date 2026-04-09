function toggleTheme(){

let body = document.body

body.classList.toggle("dark-mode")

localStorage.setItem(
"theme",
body.classList.contains("dark-mode")
)

}