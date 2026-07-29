let searchReady = false;

function initializeSearch() {
	if (searchReady) {
		return;
	}

	if (!window.PagefindUI) {
		console.error("Pagefind UI failed to load.");
		return;
	}

	new window.PagefindUI({
		element: "#docs-search-ui",
		showSubResults: true,
		showImages: false,
	});
	searchReady = true;
}

for (const button of document.querySelectorAll("[data-docs-search-open]")) {
	button.addEventListener("click", () => {
		const dialog = document.querySelector("[data-docs-search-dialog]");
		if (!dialog) {
			return;
		}

		initializeSearch();
		dialog.showModal();
		window.setTimeout(() => {
			dialog.querySelector("input")?.focus();
		}, 0);
	});
}

for (const button of document.querySelectorAll("[data-docs-search-close]")) {
	button.addEventListener("click", () => {
		button.closest("dialog")?.close();
	});
}
