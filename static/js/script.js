
document.addEventListener('DOMContentLoaded', function() {
    const pageType = document.body.getAttribute('data-page');
    const calendar = document.getElementById('calendar');
    const currentMonthYear = document.getElementById('current-month-year');
    const prevMonthBtn = document.getElementById('prev-month');
    const nextMonthBtn = document.getElementById('next-month');
    const profileForm = document.getElementById('profileForm');
    const orderButton = document.getElementById('modalBookNow');

    let currentDate = new Date();
    let changes = {};
    const monthNames = ["January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December"
    ];

    //בונה את לוח השנה
    function renderCalendar(year, month) {
        calendar.innerHTML = '';
        currentMonthYear.textContent = `${monthNames[month]} ${year}`;

        const firstDay = new Date(year, month, 1);
        const lastDay = new Date(year, month + 1, 0);

        const daysOfWeek = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
        daysOfWeek.forEach(day => {
            const dayHeader = document.createElement('div');
            dayHeader.classList.add('calendar-day', 'day-header');
            dayHeader.textContent = day;
            calendar.appendChild(dayHeader);
        });

        for (let i = 0; i < firstDay.getDay(); i++) {
            calendar.appendChild(document.createElement('div'));
        }

        for (let day = 1; day <= lastDay.getDate(); day++) {
            const dayElement = document.createElement('div');
            dayElement.classList.add('calendar-day');
            dayElement.textContent = day;

            const currentDayDate = new Date(year, month, day);
            if (currentDayDate < new Date()) {
                dayElement.classList.add('disabled');
            } else {
                // כאן, אם זה לא עמוד 'searching_do', אפשר לערוך זמינות
                if (pageType === 'searching_do') {
                    // קריאה בלבד
                    dayElement.addEventListener('click', function() {
                        if (dayElement.classList.contains('sitting') || dayElement.classList.contains('walking')) {
                            dayElement.classList.add('selected');
                            orderButton.style.display = 'inline-block';
                            orderButton.disabled = false;
                        } else {
                            alert('This date is not available for booking.');
                        }
                    });
                } else {
                    // כאן מתבצעת עריכה (toggleAvailability)
                    dayElement.addEventListener('click', function() {
                        toggleAvailability(this, year, month, day);
                    });
                }
            }
            calendar.appendChild(dayElement);
        }

        loadAvailability(year, month);
    }
    //מאפשרת למשתמש ללחוץ על יום ולהגדיר את סוג השירות  או להסיר את הבחירה, תוך שמירת השינוי באובייקט changes
    function toggleAvailability(dayElement, year, month, day) {
        const date = `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
        const currentClass = dayElement.classList.contains('sitting') ? 'sitting'
            : dayElement.classList.contains('walking') ? 'walking'
            : '';

        let newClass;
        switch(currentClass) {
            case '':
                newClass = 'sitting';
                break;
            case 'sitting':
                newClass = 'walking';
                break;
            case 'walking':
                newClass = '';
                break;
        }

        // הסר מחלקות קודמות
        dayElement.classList.remove('sitting', 'walking');
        if (newClass) {
            dayElement.classList.add(newClass);
        }
        changes[date] = newClass;
    }

    //: טוענת נתוני זמינות מהשרת
    function loadAvailability(year, month) {
        // טוען רק תאריכים is_available=1
        fetch(`/get_availability/${year}/${month + 1}`)
            .then(response => response.json())
            .then(data => {
                console.log("Fetched availability data:", data);
                Object.entries(data).forEach(([date, type]) => {
                    // חישוב את מיקום האלמנט
                    const dayDate = new Date(date);
                    const day = dayDate.getDate();
                    const firstDay = new Date(year, month, 1);
                    const dayElement = calendar.children[firstDay.getDay() + day - 1 + 7];

                    if (dayElement) {
                        if (dayDate < new Date()) {
                            // תאריך שכבר עבר, אפשר לבטל זמינות .
                            dayElement.classList.remove('sitting', 'walking');
                            changes[date] = '';
                        } else {
                            dayElement.classList.add(type); //sitting/walking
                        }
                    }
                });
            })
            .catch(error => console.error('Error loading availability:', error));
    }
    // שולחת את השינויים שהמשתמש עשה לשרת לשמירה
    function saveChanges() {
        return fetch('/save_availability', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(changes)
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                changes = {};
                return true;
            } else {
                throw new Error('Failed to save changes');
            }
        });
    }


    prevMonthBtn.addEventListener('click', function(e) {
        e.preventDefault();
        currentDate.setMonth(currentDate.getMonth() - 1);
        renderCalendar(currentDate.getFullYear(), currentDate.getMonth());
    });

    nextMonthBtn.addEventListener('click', function(e) {
        e.preventDefault();
        currentDate.setMonth(currentDate.getMonth() + 1);
        renderCalendar(currentDate.getFullYear(), currentDate.getMonth());
    });

    if (profileForm) {
        // כשלוחצים "Save Profile" , שומר קודם את השינויים ביומן
        profileForm.addEventListener('submit', function(e) {
            e.preventDefault();
            saveChanges()
                .then(() => {
                    this.submit();
                })
                .catch(error => {
                    console.error('Error saving changes:', error);
                    alert('An error occurred while saving calendar changes. Please try again.');
                });
        });
    }

    renderCalendar(currentDate.getFullYear(), currentDate.getMonth());
});
