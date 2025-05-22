document.getElementById("check-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const email = document.getElementById("email-input").value;

    const res = await fetch("/check", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
    });

    const data = await res.json();
    document.getElementById("check-result").innerText = JSON.stringify(data, null, 2);
});

document.getElementById("bulk-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const emails = document
        .getElementById("bulk-input")
        .value.split("\n")
        .map((e) => e.trim())
        .filter(Boolean);

    const res = await fetch("/bulk-check", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ emails }),
    });

    const data = await res.json();
    document.getElementById("bulk-result").innerText = JSON.stringify(data, null, 2);
});
