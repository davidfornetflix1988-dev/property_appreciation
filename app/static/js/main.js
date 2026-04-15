const form = document.getElementById("appreciation-form");
const resultsBox = document.getElementById("results");
const useResponsiveCharts = window.innerWidth <= 768;
let durationSelectionMode = "preset";


const durationPresetControl = document.getElementById("duration_preset");
const durationCustomControl = document.getElementById("duration_custom");
const timeModeControl = document.getElementById("time_mode");
const durationGroup = document.getElementById("duration_group");
const timeRangeGroup = document.getElementById("time_range_group");

function updateTimeModeUI() {
    if (!timeModeControl || !durationGroup || !timeRangeGroup) {
        return;
    }

    if (timeModeControl.value === "range") {
        durationGroup.style.display = "none";
        timeRangeGroup.style.display = "block";
    } else {
        durationGroup.style.display = "block";
        timeRangeGroup.style.display = "none";
    }
}

if (timeModeControl) {
    timeModeControl.addEventListener("change", updateTimeModeUI);
}

updateTimeModeUI();

if (durationPresetControl) {
    durationPresetControl.addEventListener("change", function () {
        durationSelectionMode = "preset";
    });
}

if (durationCustomControl) {
    durationCustomControl.addEventListener("input", function () {
        durationSelectionMode = "custom";
    });
}

console.log("main.js loaded");
console.log("Form found:", !!form);
console.log("Results box found:", !!resultsBox);

form.addEventListener("submit", async function () {
    const locationTypeEl = document.getElementById("location_type");
    const locationValueEl = document.getElementById("location_value");
    const durationPresetEl = document.getElementById("duration_preset");
    const durationCustomEl = document.getElementById("duration_custom");
    const sourceEl = document.getElementById("source");
    const timeModeEl = document.getElementById("time_mode");
    const startMonthEl = document.getElementById("start_month");
    const endMonthEl = document.getElementById("end_month");

    console.log("location_type found:", !!locationTypeEl);
    console.log("location_value found:", !!locationValueEl);
    console.log("duration_preset found:", !!durationPresetEl);
    console.log("duration_custom found:", !!durationCustomEl);
    console.log("source found:", !!sourceEl);

    if (!locationTypeEl || !locationValueEl || !durationPresetEl || !durationCustomEl || !sourceEl || !timeModeEl || !startMonthEl || !endMonthEl) {
        resultsBox.innerHTML = "<p>Form element missing. Check console.</p>";
        return;
    }

    const locationType = locationTypeEl.value;
    const locationValue = locationValueEl.value;
    const durationPreset = durationPresetEl.value;
    const durationCustom = durationCustomEl.value;
    const source = sourceEl.value;
    const timeMode = timeModeEl.value;
    const startMonth = startMonthEl.value;
    const endMonth = endMonthEl.value;
    console.log("time_mode:", timeMode);
    console.log("start_month:", startMonth);
    console.log("end_month:", endMonth);

    let payload;

    if (timeMode === "range") {
        payload = {
            location_type: locationType,
            location_value: locationValue,
            start: startMonth,
            end: endMonth,
            source: source
        };
    } else {
        payload = {
            location_type: locationType,
            location_value: locationValue,
            duration_months: Number(durationSelectionMode === "custom" ? durationCustom : durationPreset),
            source: source
        };
    }

    console.log("Submitting payload:", payload);

    resultsBox.innerHTML = "<p>Running analysis...</p>";

    try {
        const response = await fetch("/appreciation", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify(payload)
        });

        const data = await response.json();

        console.log("API response:", data);

const alignmentNote = data.alignment_note ? data.alignment_note : "N/A";

let resultsHtml = "";

if (data.results && data.results.length > 0) {
    resultsHtml = data.results.map((result) => `
    <div class="provider-result-card">
        <p><strong>Source:</strong> ${result.source}</p>
        <p><strong>Metric:</strong> ${result.metric}</p>
        <p><strong>Geography:</strong> ${result.geography}</p>
        <p><strong>Start Used:</strong> ${result.start_date_used ?? "N/A"}</p>
        <p><strong>End Used:</strong> ${result.end_date_used ?? "N/A"}</p>
        <p><strong>Percent Change:</strong> <span class="pct-value">${result.pct_change !== null ? result.pct_change : "N/A"}</span></p>
    </div>
`).join("");
} else {
    resultsHtml = "<p>No provider results returned.</p>";
}

resultsBox.innerHTML = `
    <section class="result-section">
        <h3>Request Summary</h3>
        <p><strong>Request ID:</strong> ${data.request_id}</p>
        <p><strong>Source Mode:</strong> ${data.source}</p>
        <p><strong>Time Mode:</strong> ${timeMode}</p>
        <p><strong>Time Window Used:</strong> ${timeMode === "range" ? `${startMonth} to ${endMonth}` : `${durationSelectionMode === "custom" ? durationCustom : durationPreset} month(s)`}</p>
    </section>

    <section class="result-section">
        <h3>Provider Results</h3>
        ${resultsHtml}
    </section>

    <section class="result-section">
        <h3>Comparison Notes</h3>
        <p><strong>Latest End:</strong> ${data.latest_end ?? "N/A"}</p>
        <p><strong>Aligned End:</strong> ${data.aligned_end ?? "N/A"}</p>
        <p><strong>Alignment Note:</strong> ${alignmentNote}</p>
    </section>

    <section class="result-section">
        <h3>Plots</h3>

        <div class="plot-block">
            <h4>Final Summary</h4>
            <canvas id="summary-bar-chart"></canvas>
        </div>

        <div class="plot-block">
            <h4>Normalized Performance</h4>
            <canvas id="normalized-performance-chart"></canvas>
        </div>

        <div class="plot-block">
            <h4>Raw Trend Over Time (provider-native scale)</h4>

            <div class="sub-plot-block">
                <h5>Zillow Raw Trend</h5>
                <canvas id="zillow-raw-trend-chart"></canvas>
            </div>

            <div class="sub-plot-block">
                <h5>FHFA Raw Trend</h5>
                <canvas id="fhfa-raw-trend-chart"></canvas>
            </div>
        </div>
    </section>
`;

const zillowRawCanvas = document.getElementById("zillow-raw-trend-chart");
const fhfaRawCanvas = document.getElementById("fhfa-raw-trend-chart");

const zillowResults = data.results ? data.results.filter(result => result.source === "zillow") : [];
const fhfaResults = data.results ? data.results.filter(result => result.source === "fhfa") : [];

if (zillowRawCanvas && zillowResults.length > 0) {
    new Chart(zillowRawCanvas, {
        type: "line",
        data: {
            labels: zillowResults[0].series.map(point => point.date),
            datasets: zillowResults.map((result) => ({
                label: result.geography,
                data: result.series.map(point => point.value)
            }))
        },
        options: {
            responsive: useResponsiveCharts,
            maintainAspectRatio: false,
            animation: false
        }
    });
}

if (fhfaRawCanvas && fhfaResults.length > 0) {
    new Chart(fhfaRawCanvas, {
        type: "line",
        data: {
            labels: fhfaResults[0].series.map(point => point.date),
            datasets: fhfaResults.map((result) => ({
                label: result.geography,
                data: result.series.map(point => point.value)
            }))
        },
        options: {
            responsive: useResponsiveCharts,
            maintainAspectRatio: false,
            animation: false
        }
    });
}

const summaryBarCanvas = document.getElementById("summary-bar-chart");

if (summaryBarCanvas && data.results && data.results.length > 0) {
    new Chart(summaryBarCanvas, {
        type: "bar",
        data: {
            labels: data.results.map(result => result.geography),
            datasets: [
                {
                    label: "Percent Change",
                    data: data.results.map(result => result.pct_change)
                }
            ]
        },
        options: {
            responsive: useResponsiveCharts,
            maintainAspectRatio: false,
            animation: false
        }
    });
}

const normalizedPerformanceCanvas = document.getElementById("normalized-performance-chart");

if (normalizedPerformanceCanvas && data.results && data.results.length > 0) {
    const allDates = [...new Set(
        data.results.flatMap(result => (result.series || []).map(point => point.date))
    )].sort((a, b) => a.localeCompare(b));

    console.log("Normalized chart global labels:", allDates);

    const normalizedDatasets = data.results.map((result) => {
        const series = (result.series || []).slice().sort((a, b) => a.date.localeCompare(b.date));
        console.log("Normalized chart sorted series for", result.geography, series.map(point => point.date));

        const firstValue = series.length > 0 ? series[0].value : null;

        const seriesMap = new Map(
            series.map((point) => {
                if (firstValue === null || firstValue === 0) {
                    return [point.date, null];
                }
                return [point.date, ((point.value - firstValue) / firstValue) * 100];
            })
        );

        return {
            label: result.geography,
            data: allDates.map(date => seriesMap.has(date) ? seriesMap.get(date) : null),
            spanGaps: true
        };
    });

    new Chart(normalizedPerformanceCanvas, {
        type: "line",
        data: {
            labels: allDates,
            datasets: normalizedDatasets
        },
        options: {
            responsive: useResponsiveCharts,
            maintainAspectRatio: false,
            animation: false
        }
    });
}

        
    } catch (error) {
        console.error("Request failed:", error);
        resultsBox.innerHTML = "<p>Request failed. Check the console.</p>";
    }

    
});