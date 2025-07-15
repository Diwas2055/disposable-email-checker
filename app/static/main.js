document.getElementById('check-form').addEventListener('submit', async function (e) {
    e.preventDefault();
    const email = document.getElementById('email-input').value;
    const resultBox = document.getElementById('check-result');
    const button = document.getElementById('check-btn');
    const loader = document.getElementById('check-loader');

    button.disabled = true;
    loader.style.display = 'inline-block';
    resultBox.textContent = '';

    try {
        const res = await fetch('/check', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email })
        });
        const data = await res.json();
        resultBox.textContent = JSON.stringify(data, null, 2);
    } catch (error) {
        resultBox.textContent = 'Error checking email.';
    }

    loader.style.display = 'none';
    button.disabled = false;
});

document.getElementById('bulk-form').addEventListener('submit', async function (e) {
    e.preventDefault();
    const emails = document.getElementById('bulk-input').value;
    const resultBox = document.getElementById('bulk-result');
    const button = document.getElementById('bulk-btn');
    const loader = document.getElementById('bulk-loader');

    button.disabled = true;
    loader.style.display = 'inline-block';
    resultBox.textContent = '';

    try {
        const res = await fetch('/check-bulk', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ emails: emails.split('\n').map(e => e.trim()).filter(Boolean) })
        });
        const data = await res.json();
        resultBox.textContent = JSON.stringify(data, null, 2);
    } catch (error) {
        resultBox.textContent = 'Error checking emails.';
    }

    loader.style.display = 'none';
    button.disabled = false;
});
