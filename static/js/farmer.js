document.getElementById("productForm").addEventListener("submit", function(e) {
    e.preventDefault();

    const formData = new FormData(this);

    fetch("/add_product", {
        method: "POST",
        body: formData
    })
    .then(res => res.redirected ? window.location.href = res.url : res.text())
    .catch(() => alert("Error adding product"));
});
