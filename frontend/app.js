/* =========================================================
   StoreSense - Retail Sales & Inventory Copilot
   Frontend Controller
   ========================================================= */


/* =========================================================
   API HELPER
   ========================================================= */

async function getJSON(url, options = {}) {

    const response = await fetch(url, options);

    if (!response.ok) {

        const errorText = await response.text();

        throw new Error(
            errorText || `Request failed: ${response.status}`
        );
    }

    return response.json();
}


/* =========================================================
   PAGE INITIALIZATION
   ========================================================= */

async function load() {

    try {

        const [
            summary,
            attention,
            health,
            performance
        ] = await Promise.all([

            getJSON('/api/summary'),

            getJSON('/api/attention'),

            getJSON('/api/health'),

            getJSON('/api/performance')

        ]);


        updateConnectionStatus(health);

        renderSummary(summary);

        renderAttention(attention.items || []);

        renderPerformance(performance);

    }

    catch (error) {

        console.error(
            'StoreSense startup error:',
            error
        );


        const status =
            document.getElementById('status');


        if (status) {

            status.innerHTML = `
                <span class="status-dot offline"></span>
                Connection error
            `;

        }


        const sidebarStatus =
            document.getElementById('sidebarStatus');


        if (sidebarStatus) {

            sidebarStatus.textContent =
                'Connection error';

        }


        const attention =
            document.getElementById('attentionList');


        if (attention) {

            attention.innerHTML = `

                <div class="empty-state">

                    <div class="empty-icon">
                        ⚠
                    </div>

                    <h3>
                        Unable to load dashboard
                    </h3>

                    <p>
                        Please check that the StoreSense
                        server is running.
                    </p>

                </div>

            `;

        }


        showPerformanceFallback();

    }
}


/* =========================================================
   CONNECTION STATUS
   ========================================================= */

function updateConnectionStatus(health) {

    const geminiConnected =
        Boolean(
            health &&
            health.gemini_configured
        );


    const status =
        document.getElementById('status');


    if (status) {

        status.innerHTML = `

            <span class="status-dot ${
                geminiConnected
                    ? 'online'
                    : 'offline'
            }"></span>

            ${
                geminiConnected
                    ? 'Gemini connected'
                    : 'Local analytics mode'
            }

        `;

    }


    const sidebarStatus =
        document.getElementById(
            'sidebarStatus'
        );


    if (sidebarStatus) {

        sidebarStatus.textContent =

            geminiConnected

                ? 'All systems operational'

                : 'Analytics available';

    }

}


/* =========================================================
   MONEY FORMATTER
   ========================================================= */

function money(value) {

    const amount =
        Number(value || 0);


    return '₹' +
        amount.toLocaleString(
            'en-IN',
            {
                maximumFractionDigits: 0
            }
        );

}


/* =========================================================
   NUMBER FORMATTER
   ========================================================= */

function number(value) {

    return Number(
        value || 0
    ).toLocaleString(
        'en-IN'
    );

}


/* =========================================================
   SUMMARY / KPI CARDS
   ========================================================= */

function renderSummary(summary) {

    const container =
        document.getElementById(
            'summary'
        );


    if (!container) {
        return;
    }


    const cards = [

        {
            label: 'Revenue (30d)',
            value: money(
                summary.revenue_30d
            ),
            icon: '₹',
            className: 'revenue',
            target: 'performance'
        },

        {
            label: 'Units sold',
            value: number(
                summary.units_30d
            ),
            icon: '↗',
            className: 'units',
            target: 'performance'
        },

        {
            label: 'Sales records',
            value: number(
                summary.orders_30d
            ),
            icon: '▤',
            className: 'orders',
            target: 'performance'
        },

        {
            label: 'Products',
            value: number(
                summary.products
            ),
            icon: '▦',
            className: 'products',
            target: 'products'
        },

        {
            label: 'Attention items',
            value: number(
                summary.attention_count
            ),
            icon: '⚠',
            className: 'attention-count',
            target: 'attention'
        }

    ];


    container.innerHTML =
        cards.map(
            card => `

                <button
                    type="button"
                    class="card kpi-card ${card.className}"
                    onclick="handleKPIClick('${card.target}')"
                >

                    <div class="kpi-top">

                        <div class="kpi-label">
                            ${card.label}
                        </div>

                        <div class="kpi-icon">
                            ${card.icon}
                        </div>

                    </div>

                    <div class="kpi-value">
                        ${card.value}
                    </div>

                    <div class="kpi-click-hint">
                        View details →
                    </div>

                </button>

            `
        ).join('');

}


/* =========================================================
   KPI CLICK HANDLER
   ========================================================= */

function handleKPIClick(target) {

    if (target === 'performance') {

        scrollToSection(
            'business-performance'
        );

        return;
    }


    if (target === 'attention') {

        scrollToSection(
            'attention'
        );

        return;
    }


    if (target === 'products') {

        window.location.href =
            '/products';

    }

}


/* =========================================================
   SCROLL TO SECTION
   ========================================================= */

function scrollToSection(id) {

    const section =
        document.getElementById(id);


    if (!section) {
        return;
    }


    section.scrollIntoView({
        behavior: 'smooth',
        block: 'start'
    });

}


/* =========================================================
   ATTENTION ITEMS
   ========================================================= */

function renderAttention(items) {

    const container =
        document.getElementById(
            'attentionList'
        );


    if (!container) {
        return;
    }


    if (!items || items.length === 0) {

        container.innerHTML = `

            <div class="empty-state">

                <div class="empty-icon">
                    ✓
                </div>

                <h3>
                    Everything looks good
                </h3>

                <p>
                    No configured attention rules
                    are currently triggered.
                </p>

            </div>

        `;

        return;
    }


    container.innerHTML =
        items.map(
            (item, index) => {

                const priority =
                    String(
                        item.priority ||
                        'MEDIUM'
                    ).toLowerCase();


                const title =
                    escapeHTML(
                        item.title ||
                        'Attention'
                    );


                const product =
                    escapeHTML(
                        item.product ||
                        item.product_name ||
                        'Unknown product'
                    );


                const store =
                    escapeHTML(
                        item.store ||
                        item.store_name ||
                        'Unknown store'
                    );


                const message =
                    escapeHTML(
                        item.message ||
                        item.reason ||
                        ''
                    );


                const action =
                    escapeHTML(
                        item.action ||
                        'Review this item.'
                    );


                const evidence =
                    item.evidence ||
                    item.metrics ||
                    {};


                return `

                    <article
                        class="attention ${priority}"
                        tabindex="0"
                        role="button"
                        onclick="showEvidence(${safeJSONStringify(evidence)})"
                        onkeydown="handleAttentionKey(event, ${safeJSONStringify(evidence)})"
                    >

                        <div class="attention-main">

                            <div class="attention-icon">
                                ${getAttentionIcon(
                                    item.type
                                )}
                            </div>


                            <div class="attention-content">

                                <div class="attention-heading">

                                    <h3>
                                        ${title}: ${product}
                                    </h3>

                                    <span class="tag ${priority}">
                                        ${escapeHTML(
                                            String(
                                                item.priority ||
                                                'MEDIUM'
                                            )
                                        )}
                                    </span>

                                </div>


                                <div class="attention-location">
                                    ${store}
                                </div>


                                <p class="attention-message">
                                    ${message}
                                </p>


                                <div class="attention-action">

                                    <span class="action-label">
                                        Recommended action
                                    </span>

                                    <span class="action-text">
                                        ${action}
                                    </span>

                                </div>


                                <button
                                    type="button"
                                    class="evidence-btn"
                                    onclick="event.stopPropagation(); showEvidence(${safeJSONStringify(evidence)})"
                                >

                                    <span>
                                        ⌕
                                    </span>

                                    Show evidence

                                </button>

                            </div>

                        </div>

                    </article>

                `;

            }
        ).join('');

}


/* =========================================================
   ATTENTION KEYBOARD SUPPORT
   ========================================================= */

function handleAttentionKey(
    event,
    evidence
) {

    if (
        event.key === 'Enter' ||
        event.key === ' '
    ) {

        event.preventDefault();

        showEvidence(evidence);

    }

}


/* =========================================================
   ATTENTION ICONS
   ========================================================= */

function getAttentionIcon(type) {

    switch (
        String(type || '').toLowerCase()
    ) {

        case 'stockout':
        case 'stock-out':
        case 'stock_out':

            return '⚠';


        case 'slow_moving':
        case 'slow-moving':
        case 'slow':

            return '◴';


        case 'non_moving':
        case 'non-moving':

            return '◴';


        case 'sales_drop':
        case 'sales-drop':
        case 'salesdrop':

            return '↓';


        case 'sales_spike':
        case 'sales-spike':
        case 'salesspike':

            return '↗';


        default:

            return '!';

    }

}


/* =========================================================
   REFRESH ATTENTION
   ========================================================= */

async function loadAttention() {

    const button =
        document.querySelector(
            '.section-header .secondary-button'
        );


    if (button) {

        button.disabled = true;

        button.textContent =
            'Refreshing...';

    }


    try {

        const data =
            await getJSON(
                '/api/attention'
            );


        renderAttention(
            data.items || []
        );

    }

    catch (error) {

        console.error(
            'Attention refresh error:',
            error
        );

    }

    finally {

        if (button) {

            button.disabled = false;

            button.innerHTML =
                '↻ Refresh';

        }

    }

}


/* =========================================================
   BUSINESS PERFORMANCE
   ========================================================= */

function renderPerformance(data) {

    if (!data || !data.ok) {

        showPerformanceFallback();

        return;
    }


    const inventory =
        data.inventory || {};


    /* -----------------------------------------------------
       Revenue summary
       ----------------------------------------------------- */

    const revenueElement =
        document.getElementById(
            'performanceRevenue'
        );


    if (revenueElement) {

        const revenuePoints =
            data.revenue || [];


        const total =
            revenuePoints.reduce(
                (sum, point) =>
                    sum +
                    Number(
                        point.revenue || 0
                    ),
                0
            );


        revenueElement.textContent =
            formatCurrency(total);

    }


    /* -----------------------------------------------------
       Inventory total
       ----------------------------------------------------- */

    setText(
        'inventoryTotal',
        number(inventory.total)
    );


    /* -----------------------------------------------------
       Healthy
       ----------------------------------------------------- */

    setText(
        'inventoryHealthy',
        number(inventory.healthy)
    );


    /* -----------------------------------------------------
       Low stock
       ----------------------------------------------------- */

    setText(
        'inventoryLowStock',
        number(inventory.low_stock)
    );


    /* -----------------------------------------------------
       Stock-out
       ----------------------------------------------------- */

    setText(
        'inventoryStockout',
        number(inventory.stockout)
    );


    /* -----------------------------------------------------
       Slow moving
       ----------------------------------------------------- */

    setText(
        'inventorySlowMoving',
        number(inventory.slow_moving)
    );


    /* -----------------------------------------------------
       Feed revenue into chart
       ----------------------------------------------------- */

    renderSalesChart({
        ok: true,

        points:
            (data.revenue || []).map(
                item => ({
                    date: item.date,
                    revenue:
                        Number(
                            item.revenue || 0
                        ),
                    units_sold:
                        Number(
                            item.units_sold || 0
                        )
                })
            ),

        total_revenue:
            (data.revenue || []).reduce(
                (sum, item) =>
                    sum +
                    Number(
                        item.revenue || 0
                    ),
                0
            )
    });


    /* -----------------------------------------------------
       Update inventory health bars
       ----------------------------------------------------- */

    updateInventoryHealthBars(
        inventory
    );

}


/* =========================================================
   SET TEXT HELPER
   ========================================================= */

function setText(id, value) {

    const element =
        document.getElementById(id);


    if (element) {

        element.textContent =
            value;

    }

}


/* =========================================================
   INVENTORY HEALTH VISUALS
   ========================================================= */

function updateInventoryHealthBars(
    inventory
) {

    const total =
        Number(
            inventory.total || 0
        );


    if (total <= 0) {
        return;
    }


    const values = {

        healthy:
            Number(
                inventory.healthy || 0
            ),

        low_stock:
            Number(
                inventory.low_stock || 0
            ),

        stockout:
            Number(
                inventory.stockout || 0
            ),

        slow_moving:
            Number(
                inventory.slow_moving || 0
            )

    };


    Object.entries(values)
        .forEach(
            ([key, value]) => {

                const percentage =
                    Math.min(
                        (
                            value /
                            total
                        ) * 100,
                        100
                    );


                const selectors = [

                    `#inventoryBar-${key}`,

                    `[data-inventory-bar="${key}"]`

                ];


                selectors.forEach(
                    selector => {

                        const element =
                            document.querySelector(
                                selector
                            );


                        if (element) {

                            element.style.width =
                                `${percentage}%`;

                        }

                    }
                );

            }
        );

}


/* =========================================================
   PERFORMANCE FALLBACK
   ========================================================= */

function showPerformanceFallback() {

    setText(
        'performanceRevenue',
        'Data unavailable'
    );


    setText(
        'inventoryTotal',
        '—'
    );


    setText(
        'inventoryHealthy',
        '—'
    );


    setText(
        'inventoryLowStock',
        '—'
    );


    setText(
        'inventoryStockout',
        '—'
    );


    setText(
        'inventorySlowMoving',
        '—'
    );


    showChartFallback();

}


/* =========================================================
   QUICK QUESTION
   ========================================================= */

async function ask(question) {

    const input =
        document.getElementById(
            'question'
        );


    if (!input) {
        return;
    }


    input.value =
        question;


    await sendQuestion();

}


/* =========================================================
   ENTER KEY SUPPORT
   ========================================================= */

function handleQuestionKey(event) {

    if (
        event.key === 'Enter' &&
        !event.shiftKey
    ) {

        event.preventDefault();

        sendQuestion();

    }

}


/* =========================================================
   SEND COPILOT QUESTION
   ========================================================= */

async function sendQuestion() {

    const input =
        document.getElementById(
            'question'
        );


    const answer =
        document.getElementById(
            'answer'
        );


    if (!input || !answer) {
        return;
    }


    const question =
        input.value.trim();


    if (!question) {

        input.focus();

        return;

    }


    answer.innerHTML = `

        <div class="copilot-loading">

            <div class="loading-spinner"></div>

            <div>

                <strong>
                    Analyzing your retail data...
                </strong>

                <p>
                    StoreSense is checking verified
                    sales and inventory evidence.
                </p>

            </div>

        </div>

    `;


    try {

        const result =
            await getJSON(
                '/api/copilot',
                {

                    method: 'POST',

                    headers: {
                        'Content-Type':
                            'application/json'
                    },

                    body: JSON.stringify({
                        question: question
                    })

                }
            );


        answer.innerHTML =
            renderMarkdown(
                result.answer ||
                'No answer was returned.'
            );


    }

    catch (error) {

        console.error(
            'Copilot error:',
            error
        );


        answer.innerHTML = `

            <div class="copilot-error">

                <div class="error-icon">
                    ⚠
                </div>

                <div>

                    <strong>
                        Unable to process the question.
                    </strong>

                    <p>
                        StoreSense could not retrieve
                        the requested analysis.
                        Please try again.
                    </p>

                </div>

            </div>

        `;

    }

}


/* =========================================================
   MARKDOWN RENDERER
   ========================================================= */

function renderMarkdown(text) {

    if (!text) {
        return '';
    }


    let html =
        String(text);


    /* Escape HTML */

    html = html
        .replace(
            /&/g,
            '&amp;'
        )
        .replace(
            /</g,
            '&lt;'
        )
        .replace(
            />/g,
            '&gt;'
        );


    /* Remove markdown escaping */

    html = html.replace(
        /\\([*_#-])/g,
        '$1'
    );


    /* Horizontal rules */

    html = html.replace(
        /^\s*---\s*$/gm,
        '<hr>'
    );


    /* Headings */

    html = html.replace(
        /^###\s+(.+)$/gm,
        '<h3>$1</h3>'
    );


    html = html.replace(
        /^##\s+(.+)$/gm,
        '<h2>$1</h2>'
    );


    html = html.replace(
        /^#\s+(.+)$/gm,
        '<h1>$1</h1>'
    );


    /* Bold */

    html = html.replace(
        /\*\*(.+?)\*\*/g,
        '<strong>$1</strong>'
    );


    /* Italic */

    html = html.replace(
        /(?<!\*)\*([^*\n]+)\*(?!\*)/g,
        '<em>$1</em>'
    );


    /* Bullet points */

    html = html.replace(
        /^\s*[-*]\s+(.+)$/gm,
        '<div class="copilot-bullet">• $1</div>'
    );


    /* Numbered lists */

    html = html.replace(
        /^\s*\d+\.\s+(.+)$/gm,
        '<div class="copilot-numbered">$1</div>'
    );


    /* Line breaks */

    html = html.replace(
        /\n{2,}/g,
        '<br>'
    );


    html = html.replace(
        /\n/g,
        '<br>'
    );


    /* Clean breaks */

    html = html

        .replace(
            /(<br>)+(<h[1-3]>)/g,
            '$2'
        )

        .replace(
            /(<\/h[1-3]>)(<br>)+/g,
            '$1'
        )

        .replace(
            /(<br>)+(<hr>)/g,
            '$2'
        )

        .replace(
            /(<hr>)(<br>)+/g,
            '$1'
        )

        .replace(
            /(<br>)+(<div class="copilot-bullet">)/g,
            '$2'
        )

        .replace(
            /(<\/div>)(<br>)+/g,
            '$1'
        );


    return html;

}


/* =========================================================
   EVIDENCE MODAL
   ========================================================= */

function showEvidence(evidence) {

    const modal =
        document.getElementById(
            'modal'
        );


    const content =
        document.getElementById(
            'modalContent'
        );


    if (!modal || !content) {
        return;
    }


    if (
        !evidence ||
        Object.keys(evidence).length === 0
    ) {

        content.innerHTML = `

            <div class="empty-state">

                <p>
                    No additional evidence is available.
                </p>

            </div>

        `;


        modal.classList.remove(
            'hidden'
        );


        return;

    }


    content.innerHTML = `

        <div class="evidence-grid">

            ${
                Object.entries(evidence)
                    .map(
                        ([key, value]) => `

                            <div class="evidence-cell">

                                <div class="evidence-key">
                                    ${formatEvidenceKey(key)}
                                </div>

                                <div class="evidence-value">
                                    ${formatEvidenceValue(value)}
                                </div>

                            </div>

                        `
                    )
                    .join('')
            }

        </div>

    `;


    modal.classList.remove(
        'hidden'
    );

}


/* =========================================================
   FORMAT EVIDENCE KEY
   ========================================================= */

function formatEvidenceKey(key) {

    return escapeHTML(

        String(key)

            .replace(
                /_/g,
                ' '
            )

            .replace(
                /\b\w/g,
                letter =>
                    letter.toUpperCase()
            )

    );

}


/* =========================================================
   FORMAT EVIDENCE VALUE
   ========================================================= */

function formatEvidenceValue(value) {

    if (
        value === null ||
        value === undefined
    ) {

        return '—';

    }


    if (
        typeof value === 'number'
    ) {

        return escapeHTML(
            value.toLocaleString(
                'en-IN'
            )
        );

    }


    return escapeHTML(
        String(value)
    );

}


/* =========================================================
   CLOSE MODAL
   ========================================================= */

function closeModal() {

    const modal =
        document.getElementById(
            'modal'
        );


    if (modal) {

        modal.classList.add(
            'hidden'
        );

    }

}


/* =========================================================
   SALES CHART
   ========================================================= */

async function loadSalesChart() {

    try {

        const data =
            await getJSON(
                '/api/sales/trend'
            );


        renderSalesChart(
            data
        );

    }

    catch (error) {

        console.error(
            'Sales chart failed:',
            error
        );


        showChartFallback();

    }

}


/* =========================================================
   RENDER SALES CHART
   ========================================================= */

function renderSalesChart(data) {

    const points =
        data.points || [];


    if (!points.length) {

        showChartFallback();

        return;

    }


    const line =
        document.getElementById(
            'salesLine'
        );


    const area =
        document.getElementById(
            'salesArea'
        );


    const pointsGroup =
        document.getElementById(
            'salesPoints'
        );


    const dates =
        document.getElementById(
            'chartDates'
        );


    if (
        !line ||
        !area ||
        !pointsGroup
    ) {

        return;

    }


    const width = 900;

    const height = 300;

    const paddingTop = 25;

    const paddingBottom = 30;


    const chartHeight =
        height -
        paddingTop -
        paddingBottom;


    const values =
        points.map(
            item =>
                Number(
                    item.revenue
                ) || 0
        );


    const maxValue =
        Math.max(
            ...values,
            1
        );


    const minValue =
        Math.min(
            ...values,
            0
        );


    const range =
        Math.max(
            maxValue -
            minValue,
            1
        );


    const coords =
        points.map(
            (item, index) => {

                const x =
                    points.length === 1

                        ? width / 2

                        : (
                            index /
                            (
                                points.length -
                                1
                            )
                        ) * width;


                const normalized =
                    (
                        Number(
                            item.revenue
                        ) -
                        minValue
                    ) / range;


                const y =
                    paddingTop +
                    chartHeight -
                    normalized *
                    chartHeight;


                return {

                    x,
                    y,

                    revenue:
                        Number(
                            item.revenue
                        ) || 0,

                    units:
                        Number(
                            item.units_sold
                        ) || 0,

                    date:
                        item.date

                };

            }
        );


    /* -----------------------------------------------------
       Line
       ----------------------------------------------------- */

    const linePath =
        coords
            .map(
                (point, index) =>
                    `${
                        index === 0
                            ? 'M'
                            : 'L'
                    } ${point.x} ${point.y}`
            )
            .join(' ');


    const areaPath =
        `${linePath}
         L ${width} ${height - paddingBottom}
         L 0 ${height - paddingBottom}
         Z`;


    line.setAttribute(
        'd',
        linePath
    );


    area.setAttribute(
        'd',
        areaPath
    );


    /* -----------------------------------------------------
       Points
       ----------------------------------------------------- */

    pointsGroup.innerHTML = '';


    coords.forEach(
        point => {

            const circle =
                document.createElementNS(
                    'http://www.w3.org/2000/svg',
                    'circle'
                );


            circle.setAttribute(
                'cx',
                point.x
            );


            circle.setAttribute(
                'cy',
                point.y
            );


            circle.setAttribute(
                'r',
                '5'
            );


            circle.setAttribute(
                'class',
                'sales-point'
            );


            circle.setAttribute(
                'tabindex',
                '0'
            );


            /* Hover */

            circle.addEventListener(
                'mouseenter',
                event => {

                    showChartTooltip(
                        event,
                        point
                    );

                }
            );


            circle.addEventListener(
                'mouseleave',
                hideChartTooltip
            );


            /* Click */

            circle.addEventListener(
                'click',
                () => {

                    showChartPointDetails(
                        point
                    );

                }
            );


            /* Keyboard */

            circle.addEventListener(
                'keydown',
                event => {

                    if (
                        event.key ===
                            'Enter' ||
                        event.key ===
                            ' '
                    ) {

                        event.preventDefault();

                        showChartPointDetails(
                            point
                        );

                    }

                }
            );


            pointsGroup.appendChild(
                circle
            );

        }
    );


    /* -----------------------------------------------------
       Dates
       ----------------------------------------------------- */

    if (dates) {

        dates.innerHTML = '';


        const dateIndexes = [

            0,

            Math.floor(
                points.length / 3
            ),

            Math.floor(
                points.length * 2 / 3
            ),

            points.length - 1

        ];


        [
            ...new Set(
                dateIndexes
            )
        ].forEach(
            index => {

                if (
                    !points[index]
                ) {
                    return;
                }


                const span =
                    document.createElement(
                        'span'
                    );


                span.textContent =
                    formatChartDate(
                        points[index].date
                    );


                dates.appendChild(
                    span
                );

            }
        );

    }


    /* -----------------------------------------------------
       Total revenue
       ----------------------------------------------------- */

    const totalRevenue =
        data.total_revenue ??
        points.reduce(
            (sum, point) =>
                sum +
                Number(
                    point.revenue || 0
                ),
            0
        );


    const revenueElement =
        document.getElementById(
            'chartRevenue'
        );


    if (revenueElement) {

        revenueElement.textContent =
            formatCurrency(
                totalRevenue
            );

    }


    /* -----------------------------------------------------
       Trend
       ----------------------------------------------------- */

    const trendElement =
        document.getElementById(
            'chartTrend'
        );


    if (
        trendElement &&
        points.length >= 2
    ) {

        const first =
            Number(
                points[0].revenue
            ) || 0;


        const last =
            Number(
                points[
                    points.length - 1
                ].revenue
            ) || 0;


        if (first === 0) {

            trendElement.textContent =
                'New sales data';

        }

        else {

            const change =
                (
                    (
                        last -
                        first
                    ) / first
                ) * 100;


            trendElement.textContent =
                `${
                    change >= 0
                        ? '↑'
                        : '↓'
                } ${
                    Math.abs(
                        change
                    ).toFixed(1)
                }%`;

        }

    }

}


/* =========================================================
   CLICKABLE CHART POINT DETAILS
   ========================================================= */

function showChartPointDetails(
    point
) {

    const modal =
        document.getElementById(
            'modal'
        );


    const content =
        document.getElementById(
            'modalContent'
        );


    if (
        !modal ||
        !content
    ) {
        return;
    }


    content.innerHTML = `

        <div class="chart-detail">

            <div class="chart-detail-header">

                <span class="chart-detail-label">
                    Sales on
                </span>

                <strong>
                    ${formatChartDate(
                        point.date
                    )}
                </strong>

            </div>


            <div class="chart-detail-grid">

                <div class="evidence-cell">

                    <div class="evidence-key">
                        Revenue
                    </div>

                    <div class="evidence-value">
                        ${formatCurrency(
                            point.revenue
                        )}
                    </div>

                </div>


                <div class="evidence-cell">

                    <div class="evidence-key">
                        Units sold
                    </div>

                    <div class="evidence-value">
                        ${number(
                            point.units
                        )}
                    </div>

                </div>

            </div>

        </div>

    `;


    modal.classList.remove(
        'hidden'
    );

}


/* =========================================================
   CHART TOOLTIP
   ========================================================= */

function showChartTooltip(
    event,
    point
) {

    const tooltip =
        document.getElementById(
            'chartTooltip'
        );


    if (!tooltip) {
        return;
    }


    tooltip.innerHTML = `

        <strong>
            ${formatCurrency(
                point.revenue
            )}
        </strong>

        <span>
            ${formatChartDate(
                point.date
            )}
        </span>

        <small>
            ${number(
                point.units
            )} units
        </small>

    `;


    const svg =
        event.target
            .ownerSVGElement;


    if (!svg) {
        return;
    }


    const rect =
        svg.getBoundingClientRect();


    const x =
        (
            point.x /
            900
        ) * rect.width;


    const y =
        (
            point.y /
            300
        ) * rect.height;


    tooltip.style.left =
        `${x}px`;


    tooltip.style.top =
        `${y}px`;


    tooltip.classList.remove(
        'hidden'
    );

}


/* =========================================================
   HIDE CHART TOOLTIP
   ========================================================= */

function hideChartTooltip() {

    const tooltip =
        document.getElementById(
            'chartTooltip'
        );


    if (tooltip) {

        tooltip.classList.add(
            'hidden'
        );

    }

}


/* =========================================================
   CHART FALLBACK
   ========================================================= */

function showChartFallback() {

    const line =
        document.getElementById(
            'salesLine'
        );


    const area =
        document.getElementById(
            'salesArea'
        );


    if (line) {

        line.setAttribute(
            'd',
            ''
        );

    }


    if (area) {

        area.setAttribute(
            'd',
            ''
        );

    }


    const points =
        document.getElementById(
            'salesPoints'
        );


    if (points) {

        points.innerHTML = '';

    }


    const dates =
        document.getElementById(
            'chartDates'
        );


    if (dates) {

        dates.innerHTML = `

            <span>
                No sales trend data available
            </span>

        `;

    }


    setText(
        'chartRevenue',
        '₹0'
    );


    setText(
        'chartTrend',
        '—'
    );

}


/* =========================================================
   CURRENCY
   ========================================================= */

function formatCurrency(value) {

    return new Intl.NumberFormat(
        'en-IN',
        {
            style: 'currency',
            currency: 'INR',
            maximumFractionDigits: 0
        }
    ).format(
        Number(value || 0)
    );

}


/* =========================================================
   CHART DATE
   ========================================================= */

function formatChartDate(value) {

    const date =
        new Date(value);


    if (
        Number.isNaN(
            date.getTime()
        )
    ) {

        return String(
            value || ''
        );

    }


    return date.toLocaleDateString(
        'en-IN',
        {
            day: '2-digit',
            month: 'short'
        }
    );

}


/* =========================================================
   ESCAPE HTML
   ========================================================= */

function escapeHTML(value) {

    return String(
        value ?? ''
    )

        .replace(
            /&/g,
            '&amp;'
        )

        .replace(
            /</g,
            '&lt;'
        )

        .replace(
            />/g,
            '&gt;'
        )

        .replace(
            /"/g,
            '&quot;'
        )

        .replace(
            /'/g,
            '&#039;'
        );

}


/* =========================================================
   SAFE JSON FOR INLINE EVENTS
   ========================================================= */

function safeJSONStringify(value) {

    return JSON.stringify(
        value
    )

        .replace(
            /'/g,
            '&#39;'
        )

        .replace(
            /</g,
            '\\u003c'
        )

        .replace(
            />/g,
            '\\u003e'
        )

        .replace(
            /&/g,
            '\\u0026'
        );

}


/* =========================================================
   ESC KEY
   ========================================================= */

document.addEventListener(
    'keydown',
    function(event) {

        if (
            event.key ===
            'Escape'
        ) {

            closeModal();

        }

    }
);


/* =========================================================
   CLICK OUTSIDE MODAL
   ========================================================= */

document.addEventListener(
    'click',
    function(event) {

        const modal =
            document.getElementById(
                'modal'
            );


        if (
            !modal ||
            modal.classList.contains(
                'hidden'
            )
        ) {

            return;

        }


        if (
            event.target ===
            modal
        ) {

            closeModal();

        }

    }
);


/* =========================================================
   AUTO REFRESH
   ========================================================= */

setInterval(
    async function() {

        try {

            const [
                summary,
                attention,
                performance
            ] = await Promise.all([

                getJSON(
                    '/api/summary'
                ),

                getJSON(
                    '/api/attention'
                ),

                getJSON(
                    '/api/performance'
                )

            ]);


            renderSummary(
                summary
            );


            renderAttention(
                attention.items ||
                []
            );


            renderPerformance(
                performance
            );

        }

        catch (error) {

            console.warn(
                'Automatic dashboard refresh failed:',
                error
            );

        }

    },
    30000
);


/* =========================================================
   START STORE SENSE
   ========================================================= */

document.addEventListener(
    'DOMContentLoaded',
    function() {

        /*
         * load() handles:
         * summary
         * attention
         * health
         * performance
         * sales chart
         */

        load();

    }
);