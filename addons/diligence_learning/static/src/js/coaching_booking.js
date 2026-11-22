/** @odoo-module **/

const initializeDiligenceCoachingBooking = () => {
    document.querySelectorAll('.diligence-coaching-booking-form').forEach((form) => {
        const countSelect = form.querySelector('.diligence-participant-count');
        if (!countSelect) {
            return;
        }
        const updateRows = () => {
            const count = Number.parseInt(countSelect.value || '1', 10);
            form.querySelectorAll('.diligence-participant-row').forEach((row) => {
                row.style.display = Number(row.dataset.participantIndex) <= count ? '' : 'none';
            });
        };
        countSelect.addEventListener('change', updateRows);
        updateRows();
    });

    document.querySelectorAll('[data-diligence-coaching-calendar="1"]').forEach((calendar) => {
        const grid = calendar.querySelector('[data-calendar-grid]');
        const monthLabel = calendar.querySelector('[data-calendar-month]');
        const selectedLabel = calendar.querySelector('[data-calendar-selected-date]');
        const slotCountLabel = calendar.querySelector('[data-calendar-slot-count]');
        const noSlotsMessage = calendar.querySelector('[data-calendar-no-slots]');
        const slots = [...calendar.querySelectorAll('[data-slot-start]')].map((element) => {
            const rawStart = element.dataset.slotStart;
            const start = new Date(/[zZ]|[+-]\d\d:\d\d$/.test(rawStart) ? rawStart : `${rawStart}Z`);
            const dateKey = `${start.getFullYear()}-${String(start.getMonth() + 1).padStart(2, '0')}-${String(start.getDate()).padStart(2, '0')}`;
            return { element, start, dateKey };
        }).filter((slot) => !Number.isNaN(slot.start.getTime()));

        if (!grid || !slots.length) {
            return;
        }

        const slotsByDate = new Map();
        slots.forEach((slot) => {
            slotsByDate.set(slot.dateKey, [...(slotsByDate.get(slot.dateKey) || []), slot]);
        });
        let selectedDate = slots[0].dateKey;
        let month = new Date(slots[0].start.getFullYear(), slots[0].start.getMonth(), 1);
        const pageLocale = (document.documentElement.lang || navigator.language || 'en').replace('_', '-');
        let dateFormatter;
        let monthFormatter;
        const weekFormatter = (() => {
            try {
                dateFormatter = new Intl.DateTimeFormat(pageLocale, {
                    weekday: 'long', day: 'numeric', month: 'long', year: 'numeric',
                });
                monthFormatter = new Intl.DateTimeFormat(pageLocale, { month: 'long', year: 'numeric' });
                return new Intl.DateTimeFormat(pageLocale, { weekday: 'short' });
            } catch (_error) {
                dateFormatter = new Intl.DateTimeFormat('en', {
                    weekday: 'long', day: 'numeric', month: 'long', year: 'numeric',
                });
                monthFormatter = new Intl.DateTimeFormat('en', { month: 'long', year: 'numeric' });
                return new Intl.DateTimeFormat('en', { weekday: 'short' });
            }
        })();
        const timeFormatter = new Intl.DateTimeFormat(undefined, { hour: 'numeric', minute: '2-digit' });

        const selectDate = (dateKey) => {
            selectedDate = dateKey;
            const daySlots = slotsByDate.get(dateKey) || [];
            const [year, monthNumber, day] = dateKey.split('-').map(Number);
            selectedLabel.textContent = dateFormatter.format(new Date(year, monthNumber - 1, day));
            slotCountLabel.textContent = `${daySlots.length} ${daySlots.length === 1 ? 'coaching slot' : 'coaching slots'} available`;
            slots.forEach(({ element, dateKey: slotDate, start }) => {
                const visible = slotDate === selectedDate;
                element.classList.toggle('d-none', !visible);
                const time = element.querySelector('[data-slot-time]');
                if (time) {
                    time.textContent = timeFormatter.format(start);
                }
            });
            noSlotsMessage.classList.toggle('d-none', daySlots.length > 0);
            renderCalendar();
        };

        const renderCalendar = () => {
            const year = month.getFullYear();
            const monthNumber = month.getMonth();
            monthLabel.textContent = monthFormatter.format(month);
            grid.replaceChildren();

            const mondayFirstOffset = (new Date(year, monthNumber, 1).getDay() + 6) % 7;
            const daysInMonth = new Date(year, monthNumber + 1, 0).getDate();
            const weekdayLabels = Array.from({ length: 7 }, (_, index) => {
                const mondayFirstDay = (index + 1) % 7;
                const labelDate = new Date(2024, 0, 7 + mondayFirstDay);
                return weekFormatter.format(labelDate);
            });
            weekdayLabels.forEach((label) => {
                const heading = document.createElement('span');
                heading.className = 'diligence-coaching-weekday';
                heading.textContent = label;
                heading.setAttribute('role', 'columnheader');
                grid.append(heading);
            });
            for (let blank = 0; blank < mondayFirstOffset; blank += 1) {
                const spacer = document.createElement('span');
                spacer.setAttribute('aria-hidden', 'true');
                grid.append(spacer);
            }
            for (let day = 1; day <= daysInMonth; day += 1) {
                const dateKey = `${year}-${String(monthNumber + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
                const daySlots = slotsByDate.get(dateKey) || [];
                const button = document.createElement('button');
                button.type = 'button';
                button.className = 'diligence-coaching-day';
                button.textContent = String(day);
                button.disabled = daySlots.length === 0;
                button.setAttribute('role', 'gridcell');
                button.setAttribute('aria-pressed', dateKey === selectedDate ? 'true' : 'false');
                if (daySlots.length) {
                    button.classList.add('has-slots');
                    button.setAttribute('aria-label', `${dateFormatter.format(new Date(year, monthNumber, day))}, ${daySlots.length} available`);
                    const marker = document.createElement('span');
                    marker.className = 'diligence-coaching-day-marker';
                    marker.setAttribute('aria-hidden', 'true');
                    button.append(marker);
                    button.addEventListener('click', () => selectDate(dateKey));
                }
                grid.append(button);
            }
        };

        calendar.querySelector('[data-calendar-prev]').addEventListener('click', () => {
            month = new Date(month.getFullYear(), month.getMonth() - 1, 1);
            renderCalendar();
        });
        calendar.querySelector('[data-calendar-next]').addEventListener('click', () => {
            month = new Date(month.getFullYear(), month.getMonth() + 1, 1);
            renderCalendar();
        });
        selectDate(selectedDate);
    });
};

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeDiligenceCoachingBooking, { once: true });
} else {
    initializeDiligenceCoachingBooking();
}
