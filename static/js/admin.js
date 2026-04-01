// Admin dashboard JavaScript utilities

// Auto-refresh results every 5 seconds for active questions
document.addEventListener('DOMContentLoaded', function() {
    const activeQuestion = document.querySelector('.active-question');
    if (activeQuestion) {
        const questionId = activeQuestion.querySelector('[onclick*="loadResults"]')
            ?.getAttribute('onclick')
            ?.match(/loadResults\('([^']+)'\)/)?.[1];

        if (questionId) {
            setInterval(() => loadResults(questionId), 5000);
        }
    }
});
