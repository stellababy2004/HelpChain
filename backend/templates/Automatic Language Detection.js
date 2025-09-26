document.querySelector('form').onsubmit = function() {
    var username = document.querySelector('input[name="username"]').value;
    var password = document.querySelector('input[name="password"]').value;
    if (username == "admin" && password == "help2025!") {
        sessionStorage.setItem("admin_logged_in", "true");
        window.location.href = "{{ url_for('admin_dashboard') }}";
    } else {
        alert("Невалидно потребителско име или парола.");
    }
    return false;
};

# Автоматично определяне на език от HTTP headers или user preferences
session['language'] = translation_service.detect_user_language(request.headers, user_id)