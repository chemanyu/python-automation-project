def create_button(master, text, command):
    button = Button(master, text=text, command=command)
    button.pack(side=RIGHT, padx=10, pady=10)
    return button

def navigate_to_next_page(current_page, next_page):
    current_page.destroy()
    next_page()