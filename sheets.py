def pick_sheet(W, H):

    sheets = [(2440,1220), (3000,1500)]

    for sw, sh in sheets:
        if W <= sw and H <= sh:
            return sw, sh

    return W, H
