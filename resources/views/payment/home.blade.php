<form id="payment-form">
    <input type="number" id="amount" name="amount" min="1" step="0.01" placeholder="Enter amount (min RM 1.00)" required>
    <div id="card-element"></div>
    <button type="submit" id="submit">Pay</button>
</form>


<meta name="csrf-token" content="{{ csrf_token() }}">

<script src="https://js.stripe.com/v3/"></script>
<script>
    // Load Stripe
    const stripe = Stripe('{{ env("STRIPE_KEY") }}');
    const elements = stripe.elements();
    const cardElement = elements.create('card');
    cardElement.mount('#card-element');

    const form = document.getElementById('payment-form');

    form.addEventListener('submit', async (event) => {
        event.preventDefault();

        // Get amount input value
        const amount = parseFloat(document.getElementById('amount').value);

        if (isNaN(amount) || amount < 1) {
            alert('The minimum payment amount is RM 1.00');
            return;
        }

        try {
            // Make a POST request to create a PaymentIntent
            const response = await fetch('/payment-intent', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRF-TOKEN': document.querySelector('meta[name="csrf-token"]').getAttribute('content'), // Include CSRF token for Laravel
                },
                body: JSON.stringify({ amount: amount }), // Send the dynamic amount
            });

            if (!response.ok) {
                throw new Error(`HTTP error! Status: ${response.status}`);
            }

            const { clientSecret } = await response.json();

            // Confirm the card payment
            const { error, paymentIntent } = await stripe.confirmCardPayment(clientSecret, {
                payment_method: {
                    card: cardElement,
                },
            });

            if (error) {
                alert(`Payment failed: ${error.message}`);
            } else {
                alert('Payment successful!');
            }
        } catch (error) {
            console.error('Error:', error);
            alert('Something went wrong while processing your payment. Please try again.');
        }
    });
</script>
