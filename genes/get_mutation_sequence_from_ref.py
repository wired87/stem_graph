def get_mutation_sequence_from_ref(inject_mutation_at, start, end, alt_base, full_sequence):
    mutated_sequence = None
    if inject_mutation_at and alt_base:
        # Der Index im String berechnet sich aus: Ziel-Position MINUS Start-Position des Gens
        mutation_index = inject_mutation_at - start

        # Sicherheits-Check, ob der Index innerhalb des Strings liegt
        if 0 <= mutation_index < len(full_sequence):
            mutated_sequence = (
                    full_sequence[:mutation_index] +
                    f"[{alt_base.upper()}]" +
                    full_sequence[mutation_index + 1:]
            )
        else:
            print(f"Mutaions-Position {inject_mutation_at} liegt außerhalb des Gens ({start}-{end})")
    return mutated_sequence