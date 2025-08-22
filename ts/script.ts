const sidebarLinks = document.querySelectorAll(".sidebar-menu li a");

sidebarLinks.forEach(link => {
  link.addEventListener("click", (e) => {
    e.preventDefault();
    console.log(`Clicked on ${link.textContent}`);
  });
});
