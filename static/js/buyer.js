// ✅ Load cart count on page load
updateCartCount();

// ✅ Handle Add to Cart
document.querySelectorAll(".cart-form").forEach(form => {
    form.addEventListener("submit", async (e) => {
        e.preventDefault();

        const productId = form.dataset.id;
        const quantity = form.querySelector("input").value;

        const response = await fetch(`/add_to_cart/${productId}`, {
            method: "POST",
            headers: {
                "Content-Type": "application/x-www-form-urlencoded"
            },
            body: `quantity=${quantity}`
        });

        const result = await response.json();

        if (result.success) {
            showToast();
            updateCartCount();
        }
    });
});

function updateCartCount() {
    fetch('/cart_count')
    .then(res => res.json())
    .then(data => {
        document.getElementById("cartCount").innerText = data.count;
    });
}

function showToast() {
    const toast = document.getElementById("toast");
    toast.classList.add("show");

    setTimeout(() => {
        toast.classList.remove("show");
    }, 2000);
}
