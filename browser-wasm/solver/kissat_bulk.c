/* SPDX-License-Identifier: MIT
 * Project-owned adapter. Kissat itself retains its separate MIT notice.
 */
#include "kissat.h"
#include <stddef.h>

/* DIMACS signed literals, with a zero after every clause (including empty).
 * The input memory belongs to the caller and can be freed after this returns.
 */
void kissat_add_buffer(kissat *solver, const int *literals, size_t length) {
  for (size_t i = 0; i < length; ++i)
    kissat_add(solver, literals[i]);
}
