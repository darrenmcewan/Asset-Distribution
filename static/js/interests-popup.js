/**
 * Interests Popup — shows interested users when clicking the count in admin assets table.
 * Expects global `assetInterests` object (already provided by admin/assets.html).
 */

function showInterestsPopup(assetId, assetName) {
    var popup = document.getElementById('interestsPopup');
    var title = document.getElementById('interestsPopupTitle');
    var body = document.getElementById('interestsPopupBody');

    title.textContent = 'Interested: ' + assetName;

    var interested = (typeof assetInterests !== 'undefined') ? (assetInterests[assetId] || []) : [];

    if (interested.length === 0) {
        body.innerHTML = '<p class="no-interests">No interests</p>';
    } else {
        var html = '<ul>';
        interested.forEach(function(item) {
            var label = item.username;
            if (item.branch) {
                label += ' <span style="color: var(--color-text-muted);">(' + item.branch + ')</span>';
            }
            html += '<li>' + label + '</li>';
        });
        html += '</ul>';
        body.innerHTML = html;
    }

    popup.style.display = 'flex';
}

function hideInterestsPopup() {
    document.getElementById('interestsPopup').style.display = 'none';
}

// Dismiss on click outside the card
document.addEventListener('click', function(e) {
    var popup = document.getElementById('interestsPopup');
    if (popup.style.display === 'flex') {
        var card = popup.querySelector('.interests-popup-card');
        if (!card.contains(e.target) && !e.target.classList.contains('btn-interest-count')) {
            hideInterestsPopup();
        }
    }
});

// Dismiss on Escape key
document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
        var popup = document.getElementById('interestsPopup');
        if (popup.style.display === 'flex') {
            hideInterestsPopup();
        }
    }
});
