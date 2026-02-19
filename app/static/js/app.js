// YardHarvest UI Utilities

document.addEventListener('DOMContentLoaded', function() {

    // Image preview on file input change
    document.querySelectorAll('input[type="file"]').forEach(function(input) {
        input.addEventListener('change', function(e) {
            const file = e.target.files[0];
            if (!file) return;

            // Find or create preview element
            let preview = input.parentElement.querySelector('.image-preview');
            if (!preview) {
                preview = document.createElement('img');
                preview.classList.add('image-preview', 'mt-2', 'd-block');
                input.parentElement.appendChild(preview);
            }

            const reader = new FileReader();
            reader.onload = function(ev) {
                preview.src = ev.target.result;
            };
            reader.readAsDataURL(file);
        });
    });

    // Toggle delivery radius field visibility
    const deliveryCheck = document.getElementById('delivery_available');
    const radiusGroup = document.getElementById('delivery-radius-group');
    if (deliveryCheck && radiusGroup) {
        function toggleRadius() {
            radiusGroup.style.display = deliveryCheck.checked ? 'block' : 'none';
        }
        toggleRadius();
        deliveryCheck.addEventListener('change', toggleRadius);
    }

    // Toggle custom address fields
    const useProfileAddr = document.getElementById('use_profile_address');
    const customAddrGroup = document.getElementById('custom-address-group');
    if (useProfileAddr && customAddrGroup) {
        function toggleAddr() {
            customAddrGroup.style.display = useProfileAddr.checked ? 'none' : 'block';
        }
        toggleAddr();
        useProfileAddr.addEventListener('change', toggleAddr);
    }

    // Auto-scroll chat to bottom
    const chatContainer = document.querySelector('.chat-container');
    if (chatContainer) {
        chatContainer.scrollTop = chatContainer.scrollHeight;
    }

    // Confirm delete actions
    document.querySelectorAll('.confirm-delete').forEach(function(form) {
        form.addEventListener('submit', function(e) {
            if (!confirm('Are you sure you want to remove this listing?')) {
                e.preventDefault();
            }
        });
    });

    // Auto-dismiss alerts after 5 seconds
    document.querySelectorAll('.alert-dismissible').forEach(function(alert) {
        setTimeout(function() {
            var bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
            bsAlert.close();
        }, 5000);
    });
});
