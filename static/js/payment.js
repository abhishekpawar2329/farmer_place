// ===== PAYMENT MODE TOGGLE =====
const radios     = document.querySelectorAll('input[name="payment_mode"]');
const upiField   = document.getElementById('upiField');
const cardField  = document.getElementById('cardField');
const netField   = document.getElementById('netField');

function showSubField(mode) {
    upiField.classList.add('hidden');
    cardField.classList.add('hidden');
    netField.classList.add('hidden');

    if (mode === 'UPI')          upiField.classList.remove('hidden');
    if (mode === 'Card')         cardField.classList.remove('hidden');
    if (mode === 'Net Banking')  netField.classList.remove('hidden');
}

radios.forEach(radio => {
    radio.addEventListener('change', () => showSubField(radio.value));
});

// Show UPI by default (first option)
showSubField('UPI');

// ===== CARD NUMBER FORMATTER (adds spaces every 4 digits) =====
const cardInput = document.getElementById('cardNumber');
if (cardInput) {
    cardInput.addEventListener('input', (e) => {
        let val = e.target.value.replace(/\D/g, '').substring(0, 16);
        e.target.value = val.match(/.{1,4}/g)?.join(' ') || val;
    });
}

// ===== PHONE NUMBER (digits only) =====
document.querySelector('input[name="phone"]')?.addEventListener('input', (e) => {
    e.target.value = e.target.value.replace(/\D/g, '').substring(0, 10);
});

// ===== PINCODE (digits only) =====
document.querySelector('input[name="pincode"]')?.addEventListener('input', (e) => {
    e.target.value = e.target.value.replace(/\D/g, '').substring(0, 6);
});

// ===== EXPIRY FORMATTER (MM / YY) =====
document.querySelector('input[name="expiry"]')?.addEventListener('input', (e) => {
    let val = e.target.value.replace(/\D/g, '').substring(0, 4);
    if (val.length >= 3) val = val.substring(0,2) + ' / ' + val.substring(2);
    e.target.value = val;
});

// ===== FORM SUBMIT → show spinner, then success overlay =====
const form    = document.getElementById('paymentForm');
const btn     = document.getElementById('placeOrderBtn');
const label   = btn.querySelector('.btn-label');
const spinner = document.getElementById('spinner');
const overlay = document.getElementById('successOverlay');

form.addEventListener('submit', async (e) => {
    e.preventDefault();

    // Show spinner
    label.classList.add('hidden');
    spinner.classList.remove('hidden');
    btn.disabled = true;

    // Submit to Flask /checkout
    const formData = new FormData(form);

    try {
        const res = await fetch('/checkout', {
            method: 'POST',
            body: formData
        });

        // Flask redirects to /buyer_dashboard after successful checkout
        if (res.redirected || res.ok) {
            // Show success overlay
            overlay.classList.remove('hidden');
        } else {
            const text = await res.text();
            alert('Checkout failed: ' + text);
            label.classList.remove('hidden');
            spinner.classList.add('hidden');
            btn.disabled = false;
        }
    } catch (err) {
        alert('Network error. Please try again.');
        label.classList.remove('hidden');
        spinner.classList.add('hidden');
        btn.disabled = false;
    }
});
