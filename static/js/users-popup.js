/**
 * Users Popup — shows assigned/interested items when clicking counts in admin users table.
 * Expects global `userAssigned` and `userInterested` objects keyed by user ID.
 */

function showUserItemsPopup(userId, username, type) {
    const popup = document.getElementById('userItemsPopup');
    const title = document.getElementById('userItemsPopupTitle');
    const body = document.getElementById('userItemsPopupBody');

    let items;
    if (type === 'assigned') {
        title.textContent = 'Assigned: ' + username;
        items = (typeof userAssigned === 'undefined') ? [] : (userAssigned[userId] || []);
    } else {
        title.textContent = 'Interested: ' + username;
        items = (typeof userInterested === 'undefined') ? [] : (userInterested[userId] || []);
    }

    if (items.length === 0) {
        const emptyMsg = (type === 'assigned') ? 'No assigned items' : 'No interests';
        body.innerHTML = '<p class="no-interests">' + emptyMsg + '</p>';
    } else {
        let html = '<ul>';
        items.forEach(function(item) {
            html += '<li><a href="/assets/' + item.id + '/">' + item.serial + ' &mdash; ' + item.name + '</a></li>';
        });
        html += '</ul>';
        body.innerHTML = html;
    }

    popup.style.display = 'flex';
}

function hideUserItemsPopup() {
    document.getElementById('userItemsPopup').style.display = 'none';
}

// Dismiss on click outside the card
document.addEventListener('click', function(e) {
    const popup = document.getElementById('userItemsPopup');
    if (popup?.style.display === 'flex') {
        const card = popup.querySelector('.interests-popup-card');
        if (!card.contains(e.target) && !e.target.classList.contains('btn-interest-count')) {
            hideUserItemsPopup();
        }
    }
});

// Dismiss on Escape key
document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
        const popup = document.getElementById('userItemsPopup');
        if (popup?.style.display === 'flex') {
            hideUserItemsPopup();
        }
    }
});
