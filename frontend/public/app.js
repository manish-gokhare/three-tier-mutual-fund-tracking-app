const dataElement = document.getElementById("dashboard-data");
const dashboard = dataElement ? JSON.parse(dataElement.textContent) : { holdings: [] };
const money = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 2 });

function asNumber(value) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

const totalValue = dashboard.holdings.reduce((sum, holding) => sum + asNumber(holding.current_value), 0);
const totalGain = dashboard.holdings.reduce((sum, holding) => sum + asNumber(holding.gain_loss), 0);
const portfolioValue = document.getElementById("portfolio-value");
const portfolioGain = document.getElementById("portfolio-gain");
if (portfolioValue) portfolioValue.textContent = money.format(totalValue);
if (portfolioGain) {
  portfolioGain.textContent = money.format(totalGain);
  portfolioGain.classList.toggle("positive", totalGain >= 0);
  portfolioGain.classList.toggle("negative", totalGain < 0);
}

document.querySelectorAll(".gain-cell").forEach((cell) => {
  const gain = Number(cell.dataset.gain);
  if (Number.isFinite(gain)) cell.classList.add(gain >= 0 ? "positive" : "negative");
});

const toast = document.getElementById("toast");
function showToast(message, isError = false) {
  toast.textContent = message;
  toast.className = isError ? "visible error" : "visible";
  setTimeout(() => { toast.className = ""; }, 3500);
}

document.querySelectorAll(".holding-form").forEach((form) => {
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const button = form.querySelector("button");
    button.disabled = true;
    button.textContent = "Saving…";
    const values = new FormData(form);
    try {
      const response = await fetch("/api/holdings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          fund_id: form.dataset.fundId,
          units: values.get("units"),
          average_purchase_nav: values.get("average_purchase_nav"),
        }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || "Could not add holding.");
      showToast("Holding saved. Refreshing portfolio…");
      setTimeout(() => window.location.reload(), 650);
    } catch (error) {
      showToast(error.message, true);
      button.disabled = false;
      button.textContent = "Track";
    }
  });
});

const search = document.getElementById("fund-search");
if (search) search.addEventListener("input", () => {
  const query = search.value.trim().toLowerCase();
  document.querySelectorAll("#fund-table tbody tr").forEach((row) => {
    row.hidden = !row.dataset.search.includes(query);
  });
});

const dialog = document.getElementById("history-dialog");
const historyContent = document.getElementById("history-content");
const historyTitle = document.getElementById("history-title");
document.getElementById("close-dialog")?.addEventListener("click", () => dialog.close());
document.querySelectorAll(".history-button").forEach((button) => {
  button.addEventListener("click", async () => {
    historyTitle.textContent = `${button.dataset.fundName} — last 30 days`;
    historyContent.textContent = "Loading…";
    dialog.showModal();
    try {
      const response = await fetch(`/api/funds/${button.dataset.fundId}/nav?days=30`);
      const rows = await response.json();
      if (!response.ok) throw new Error(rows.detail || "Could not load NAV history.");
      historyContent.innerHTML = rows.length
        ? `<table><thead><tr><th>Date</th><th>NAV</th></tr></thead><tbody>${rows.map((row) => `<tr><td>${row.nav_date}</td><td>${money.format(row.nav)}</td></tr>`).join("")}</tbody></table>`
        : "No NAV history is available for this fund.";
    } catch (error) {
      historyContent.textContent = error.message;
    }
  });
});
