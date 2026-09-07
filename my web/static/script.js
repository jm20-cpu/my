document.addEventListener("DOMContentLoaded", function () {

    // =========================
    // SERVICE SEARCH
    // =========================

    const searchInput =
        document.getElementById("searchInput");

    const cards =
        document.querySelectorAll(".service-card");

    if (searchInput) {

        searchInput.addEventListener(
            "input",
            function () {

                const searchText =
                    searchInput.value
                        .toLowerCase()
                        .trim();

                cards.forEach(function (card) {

                    const text =
                        card.textContent.toLowerCase();

                    if (text.includes(searchText)) {

                        card.style.display = "";

                    } else {

                        card.style.display = "none";

                    }

                });

            }
        );

    }


    // =========================
    // CONTACT FORM
    // =========================

    const contactForm =
        document.getElementById("contactForm");

    if (contactForm) {

        contactForm.addEventListener(
            "submit",
            async function (event) {

                event.preventDefault();

                const formMessage =
                    document.getElementById(
                        "formMessage"
                    );

                const formData =
                    new FormData(contactForm);

                try {

                    const response =
                        await fetch(
                            "/contact",
                            {
                                method: "POST",
                                body: formData
                            }
                        );

                    const data =
                        await response.json();

                    formMessage.textContent =
                        data.message;

                    if (data.success) {

                        contactForm.reset();

                    }

                } catch (error) {

                    formMessage.textContent =
                        "Something went wrong. Please try again.";

                }

            }
        );

    }

});


// =========================
// SERVICE BUTTON
// =========================

function serviceMessage(service) {

    alert(
        "You selected: " +
        service +
        "\n\nWe'll add more information here later."
    );

}