// Alpha Edge Daily - Calendar & Digest Viewer

// Economic theory definitions with links
const THEORY_DEFINITIONS = {
    'Euler Equation': {
        desc: 'Describes optimal consumption smoothing over time: u\'(c_t) = β(1+r)u\'(c_{t+1})',
        link: 'https://en.wikipedia.org/wiki/Euler_equations_(fluid_dynamics)#Euler_equation_in_economics'
    },
    'Keynesian Multiplier': {
        desc: 'Shows how initial spending creates ripple effects: Multiplier = 1/(1-MPC)',
        link: 'https://en.wikipedia.org/wiki/Fiscal_multiplier'
    },
    'Cobb-Douglas': {
        desc: 'Production function: Y = AK^α L^(1-α), showing how capital and labor combine',
        link: 'https://en.wikipedia.org/wiki/Cobb%E2%80%93Douglas_production_function'
    },
    'CAPM': {
        desc: 'Capital Asset Pricing Model: E(R) = Rf + β(Rm - Rf)',
        link: 'https://en.wikipedia.org/wiki/Capital_asset_pricing_model'
    },
    'Comparative Advantage': {
        desc: 'Countries benefit from trade by specializing in what they produce most efficiently',
        link: 'https://en.wikipedia.org/wiki/Comparative_advantage'
    },
    'Taylor Rule': {
        desc: 'How central banks set interest rates based on inflation and output gaps',
        link: 'https://en.wikipedia.org/wiki/Taylor_rule'
    },
    'Deadweight Loss': {
        desc: 'Economic inefficiency from taxes or monopolies: the value destroyed',
        link: 'https://en.wikipedia.org/wiki/Deadweight_loss'
    },
    'Nash Equilibrium': {
        desc: 'Game theory: when no player benefits from changing strategy unilaterally',
        link: 'https://en.wikipedia.org/wiki/Nash_equilibrium'
    },
    'Production Possibilities Frontier': {
        desc: 'The maximum output combinations an economy can produce efficiently',
        link: 'https://en.wikipedia.org/wiki/Production%E2%80%93possibility_frontier'
    },
    'Schumpeterian Innovation': {
        desc: 'Creative destruction: new innovations replace old industries',
        link: 'https://en.wikipedia.org/wiki/Creative_destruction'
    },
    'Creative Destruction': {
        desc: 'Schumpeter\'s theory that innovation destroys old industries to create new ones',
        link: 'https://en.wikipedia.org/wiki/Creative_destruction'
    },
    'Tax Incidence': {
        desc: 'Who actually bears the burden of a tax (not always who pays it)',
        link: 'https://en.wikipedia.org/wiki/Tax_incidence'
    },
    'Markup Pricing': {
        desc: 'Firms with market power charge prices above marginal cost: μ = P/MC',
        link: 'https://en.wikipedia.org/wiki/Markup_(business)'
    },
    'Permanent Income Hypothesis': {
        desc: 'Consumption based on expected lifetime income, not current income',
        link: 'https://en.wikipedia.org/wiki/Permanent_income_hypothesis'
    },
    'Asset Pricing': {
        desc: 'Valuing financial assets based on expected future cash flows',
        link: 'https://en.wikipedia.org/wiki/Asset_pricing'
    },
    'Equity Valuation': {
        desc: 'Determining stock value: V = Σ(dividends)/(1+r)^t',
        link: 'https://en.wikipedia.org/wiki/Stock_valuation'
    },
    'Fiscal Multipliers': {
        desc: 'How government spending amplifies through the economy',
        link: 'https://en.wikipedia.org/wiki/Fiscal_multiplier'
    },
    'Regional Fiscal Multipliers': {
        desc: 'Local economic impact of spending changes in a region',
        link: 'https://en.wikipedia.org/wiki/Fiscal_multiplier'
    },
    'Game Theory': {
        desc: 'Mathematical study of strategic decision-making',
        link: 'https://en.wikipedia.org/wiki/Game_theory'
    },
    'Deterrence Games': {
        desc: 'Strategic interactions where threats prevent unwanted actions',
        link: 'https://en.wikipedia.org/wiki/Deterrence_theory'
    },
    'Rational Expectations': {
        desc: 'Agents use all available information to form expectations',
        link: 'https://en.wikipedia.org/wiki/Rational_expectations'
    },
    'Consumer Demand Theory': {
        desc: 'How consumers allocate budgets to maximize utility',
        link: 'https://en.wikipedia.org/wiki/Consumer_choice'
    },
    'MPC': {
        desc: 'Marginal Propensity to Consume: how much of extra income is spent',
        link: 'https://en.wikipedia.org/wiki/Marginal_propensity_to_consume'
    },
    'Black-Scholes': {
        desc: 'Option pricing formula: C = SN(d1) - Ke^(-rT)N(d2)',
        link: 'https://en.wikipedia.org/wiki/Black%E2%80%93Scholes_model'
    },
    'HHI': {
        desc: 'Herfindahl-Hirschman Index: measures market concentration',
        link: 'https://en.wikipedia.org/wiki/Herfindahl%E2%80%93Hirschman_index'
    },
    'Beveridge Curve': {
        desc: 'Relationship between unemployment and job vacancies',
        link: 'https://en.wikipedia.org/wiki/Beveridge_curve'
    }
};

class DigestViewer {
    constructor() {
        this.currentDate = new Date();
        this.selectedDate = null;
        this.availableDates = [];

        this.init();
    }

    async init() {
        await this.loadAvailableDates();
        this.renderCalendar();
        this.setupEventListeners();

        // Load today's digest or most recent
        const today = this.formatDate(new Date());
        if (this.availableDates.includes(today)) {
            this.loadDigest(today);
        } else if (this.availableDates.length > 0) {
            this.loadDigest(this.availableDates[0]);
        } else {
            this.showNoDigest();
        }
    }

    async loadAvailableDates() {
        try {
            const response = await fetch('digests/index.json');
            if (response.ok) {
                this.availableDates = await response.json();
                this.renderDateList();
            }
        } catch (error) {
            console.log('No index found, scanning for digests...');
            // Fallback: try to detect digests by checking recent dates
            await this.scanForDigests();
        }
    }

    async scanForDigests() {
        // Check last 30 days for digests
        const dates = [];
        const today = new Date();

        for (let i = 0; i < 30; i++) {
            const date = new Date(today);
            date.setDate(date.getDate() - i);
            const dateStr = this.formatDate(date);

            try {
                const response = await fetch(`digests/${dateStr}.md`, { method: 'HEAD' });
                if (response.ok) {
                    dates.push(dateStr);
                }
            } catch (e) {
                // File doesn't exist
            }
        }

        this.availableDates = dates;
        this.renderDateList();
    }

    formatDate(date) {
        return date.toISOString().split('T')[0];
    }

    formatDisplayDate(dateStr) {
        const date = new Date(dateStr + 'T00:00:00');
        return date.toLocaleDateString('en-US', {
            weekday: 'short',
            month: 'short',
            day: 'numeric',
            year: 'numeric'
        });
    }

    renderCalendar() {
        const calendar = document.getElementById('calendar');
        const monthLabel = document.getElementById('current-month');

        const year = this.currentDate.getFullYear();
        const month = this.currentDate.getMonth();

        monthLabel.textContent = new Date(year, month).toLocaleDateString('en-US', {
            month: 'long',
            year: 'numeric'
        });

        // Day headers
        const dayHeaders = ['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa'];
        let html = dayHeaders.map(d => `<div class="day-header">${d}</div>`).join('');

        // First day of month
        const firstDay = new Date(year, month, 1).getDay();

        // Days in month
        const daysInMonth = new Date(year, month + 1, 0).getDate();

        // Empty cells before first day
        for (let i = 0; i < firstDay; i++) {
            html += '<div class="day empty"></div>';
        }

        // Day cells
        const today = this.formatDate(new Date());

        for (let day = 1; day <= daysInMonth; day++) {
            const dateStr = `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
            const hasDigest = this.availableDates.includes(dateStr);
            const isToday = dateStr === today;
            const isSelected = dateStr === this.selectedDate;

            let classes = 'day';
            if (hasDigest) classes += ' has-digest';
            if (isToday) classes += ' today';
            if (isSelected) classes += ' selected';

            html += `<div class="${classes}" data-date="${dateStr}">${day}</div>`;
        }

        calendar.innerHTML = html;

        // Add click handlers
        calendar.querySelectorAll('.day:not(.empty)').forEach(day => {
            day.addEventListener('click', () => {
                const dateStr = day.dataset.date;
                if (this.availableDates.includes(dateStr)) {
                    this.loadDigest(dateStr);
                }
            });
        });
    }

    renderDateList() {
        const list = document.getElementById('date-list');
        list.innerHTML = this.availableDates.slice(0, 10).map(date => `
            <li data-date="${date}" class="${date === this.selectedDate ? 'active' : ''}">
                ${this.formatDisplayDate(date)}
            </li>
        `).join('');

        list.querySelectorAll('li').forEach(item => {
            item.addEventListener('click', () => {
                this.loadDigest(item.dataset.date);
            });
        });
    }

    async loadDigest(dateStr) {
        this.selectedDate = dateStr;
        this.showLoading();

        // Update calendar selection
        document.querySelectorAll('.calendar .day.selected').forEach(el => {
            el.classList.remove('selected');
        });
        const dayEl = document.querySelector(`.calendar .day[data-date="${dateStr}"]`);
        if (dayEl) dayEl.classList.add('selected');

        // Update date list selection
        document.querySelectorAll('#date-list li.active').forEach(el => {
            el.classList.remove('active');
        });
        const listEl = document.querySelector(`#date-list li[data-date="${dateStr}"]`);
        if (listEl) listEl.classList.add('active');

        try {
            const response = await fetch(`digests/${dateStr}.md`);
            if (!response.ok) throw new Error('Digest not found');

            let markdown = await response.text();

            // Remove YAML frontmatter if present
            if (markdown.startsWith('---')) {
                const endIndex = markdown.indexOf('---', 3);
                if (endIndex !== -1) {
                    markdown = markdown.substring(endIndex + 3).trim();
                }
            }

            this.showDigest(markdown);
        } catch (error) {
            console.error('Error loading digest:', error);
            this.showNoDigest();
        }
    }

    showLoading() {
        document.getElementById('loading').style.display = 'block';
        document.getElementById('no-digest').style.display = 'none';
        document.getElementById('digest').style.display = 'none';
    }

    showDigest(markdown) {
        document.getElementById('loading').style.display = 'none';
        document.getElementById('no-digest').style.display = 'none';

        const digestEl = document.getElementById('digest');
        digestEl.style.display = 'block';
        digestEl.innerHTML = marked.parse(markdown);

        // Render LaTeX equations with KaTeX
        // Only use $$ for math to avoid conflicts with currency $ symbols
        if (typeof renderMathInElement !== 'undefined') {
            renderMathInElement(digestEl, {
                delimiters: [
                    {left: '$$', right: '$$', display: false},
                    {left: '\\(', right: '\\)', display: false},
                    {left: '\\[', right: '\\]', display: true}
                ],
                throwOnError: false,
                ignoredTags: ['script', 'noscript', 'style', 'textarea', 'pre', 'code']
            });
        }

        // Add theory tooltips
        this.addTheoryTooltips(digestEl);
    }

    protectCurrencySymbols(container) {
        // Replace currency $ symbols with HTML entity to prevent KaTeX from parsing them
        // Currency pattern: $ followed by number (e.g., $40, $1.5, $100M, $23 BILLION)
        const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT);
        const textNodes = [];

        while (walker.nextNode()) {
            textNodes.push(walker.currentNode);
        }

        textNodes.forEach(node => {
            const text = node.textContent;
            // Match $ followed by numbers, possibly with decimals, K/M/B suffixes, or words like BILLION
            // But NOT math expressions like $x$ or $\alpha$
            const currencyPattern = /\$(\d+(?:\.\d+)?(?:\s*(?:K|M|B|BILLION|MILLION|TRILLION|billion|million|trillion))?)/g;

            if (currencyPattern.test(text)) {
                const newText = text.replace(currencyPattern, '&#36;$1');
                if (newText !== text) {
                    const span = document.createElement('span');
                    span.innerHTML = newText;
                    node.parentNode.replaceChild(span, node);
                }
            }
        });
    }

    addTheoryTooltips(container) {
        // Find theory sections and add tooltips
        const theoryPattern = /📚\s*Theory:?\s*(.+)/gi;
        const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT);
        const textNodes = [];

        while (walker.nextNode()) {
            textNodes.push(walker.currentNode);
        }

        textNodes.forEach(node => {
            const text = node.textContent;
            let newHTML = text;
            let hasChanges = false;

            // Check each theory definition
            Object.keys(THEORY_DEFINITIONS).forEach(theory => {
                const regex = new RegExp(`\\b${theory}\\b`, 'gi');
                if (regex.test(newHTML)) {
                    const def = THEORY_DEFINITIONS[theory];
                    newHTML = newHTML.replace(regex,
                        `<a href="${def.link}" target="_blank" class="theory-link" title="${def.desc}">${theory}</a>`
                    );
                    hasChanges = true;
                }
            });

            if (hasChanges) {
                const span = document.createElement('span');
                span.innerHTML = newHTML;
                node.parentNode.replaceChild(span, node);
            }
        });
    }

    showNoDigest() {
        document.getElementById('loading').style.display = 'none';
        document.getElementById('no-digest').style.display = 'block';
        document.getElementById('digest').style.display = 'none';
    }

    setupEventListeners() {
        document.getElementById('prev-month').addEventListener('click', () => {
            this.currentDate.setMonth(this.currentDate.getMonth() - 1);
            this.renderCalendar();
        });

        document.getElementById('next-month').addEventListener('click', () => {
            this.currentDate.setMonth(this.currentDate.getMonth() + 1);
            this.renderCalendar();
        });
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    new DigestViewer();

    // Back to Top Button
    const backToTop = document.getElementById('back-to-top');
    if (backToTop) {
        window.addEventListener('scroll', () => {
            if (window.scrollY > 400) {
                backToTop.classList.add('visible');
            } else {
                backToTop.classList.remove('visible');
            }
        });

        backToTop.addEventListener('click', () => {
            window.scrollTo({ top: 0, behavior: 'smooth' });
        });
    }
});
