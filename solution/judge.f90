module havannah_judge
   ! Holds the geometry of the hexagonal board and settles the verdict for one
   ! position. A position is a square block of characters indexed by the axial
   ! pair shifted into positive range; points off the hexagon stay '.'.
   implicit none
   private

   public :: HAV_NONE, HAV_BRIDGE, HAV_FORK, HAV_RING
   public :: dir_q, dir_r
   public :: on_board, verdict_for

   ! Codes the verdict comes back as.
   integer, parameter :: HAV_NONE = 0
   integer, parameter :: HAV_BRIDGE = 1
   integer, parameter :: HAV_FORK = 2
   integer, parameter :: HAV_RING = 3

   ! The six neighbour steps in axial coordinates.
   integer, parameter :: dir_q(6) = [ 1, -1,  0,  0,  1, -1]
   integer, parameter :: dir_r(6) = [ 0,  0,  1, -1, -1,  1]

contains

   logical function on_board(side, q, r)
      integer, intent(in) :: side
      integer, intent(in) :: q
      integer, intent(in) :: r
      on_board = (max(abs(q), abs(r), abs(-q - r)) <= side - 1)
   end function on_board

   logical function is_corner(side, q, r)
      ! A corner has one value at side-1, one at -(side-1) and one at zero.
      integer, intent(in) :: side
      integer, intent(in) :: q
      integer, intent(in) :: r
      integer :: s
      integer :: m

      s = -q - r
      m = side - 1
      is_corner = (q == m .or. r == m .or. s == m) .and. &
                  (q == -m .or. r == -m .or. s == -m) .and. &
                  (q == 0 .or. r == 0 .or. s == 0)
   end function is_corner

   integer function edge_bits(side, q, r) result(bits)
      ! One bit per hexagon edge the point sits on; zero away from the border.
      integer, intent(in) :: side
      integer, intent(in) :: q
      integer, intent(in) :: r
      integer :: s
      integer :: m

      s = -q - r
      m = side - 1
      bits = 0
      if (q == m) bits = ibset(bits, 0)
      if (q == -m) bits = ibset(bits, 1)
      if (r == m) bits = ibset(bits, 2)
      if (r == -m) bits = ibset(bits, 3)
      if (s == m) bits = ibset(bits, 4)
      if (s == -m) bits = ibset(bits, 5)
   end function edge_bits

   logical function shuts_in(side, member) result(closed)
      ! True when some point of the hexagon that is not part of the group can no
      ! longer reach the rim without stepping on the group.
      integer, intent(in) :: side
      logical, intent(in) :: member(:, :)
      logical, allocatable :: reached(:, :)
      integer, allocatable :: stack(:, :)
      integer :: m
      integer :: q
      integer :: r
      integer :: nq
      integer :: nr
      integer :: k
      integer :: top

      m = side - 1
      allocate (reached(2*side - 1, 2*side - 1))
      reached = .false.
      allocate (stack(2, (2*side - 1)**2))
      top = 0

      do q = -m, m
         do r = -m, m
            if (.not. on_board(side, q, r)) cycle
            if (member(q + side, r + side)) cycle
            if (edge_bits(side, q, r) == 0) cycle
            reached(q + side, r + side) = .true.
            top = top + 1
            stack(1, top) = q
            stack(2, top) = r
         end do
      end do

      do while (top > 0)
         q = stack(1, top)
         r = stack(2, top)
         top = top - 1
         do k = 1, 6
            nq = q + dir_q(k)
            nr = r + dir_r(k)
            if (.not. on_board(side, nq, nr)) cycle
            if (member(nq + side, nr + side)) cycle
            if (reached(nq + side, nr + side)) cycle
            reached(nq + side, nr + side) = .true.
            top = top + 1
            stack(1, top) = nq
            stack(2, top) = nr
         end do
      end do

      closed = .false.
      do q = -m, m
         do r = -m, m
            if (.not. on_board(side, q, r)) cycle
            if (member(q + side, r + side)) cycle
            if (.not. reached(q + side, r + side)) then
               closed = .true.
               return
            end if
         end do
      end do
   end function shuts_in

   integer function verdict_for(side, stones, colour) result(code)
      ! Answers which shape, if any, the given colour has already finished.
      integer, intent(in) :: side
      character, intent(in) :: stones(:, :)
      character, intent(in) :: colour
      logical, allocatable :: taken(:, :)
      logical, allocatable :: member(:, :)
      integer, allocatable :: stack(:, :)
      integer, allocatable :: group(:, :)
      logical :: any_bridge
      logical :: any_fork
      logical :: any_ring
      integer :: m
      integer :: q
      integer :: r
      integer :: nq
      integer :: nr
      integer :: k
      integer :: i
      integer :: top
      integer :: nstone
      integer :: corners
      integer :: bits

      m = side - 1
      allocate (taken(2*side - 1, 2*side - 1))
      allocate (member(2*side - 1, 2*side - 1))
      allocate (stack(2, (2*side - 1)**2))
      allocate (group(2, (2*side - 1)**2))
      taken = .false.
      any_bridge = .false.
      any_fork = .false.
      any_ring = .false.

      do q = -m, m
         do r = -m, m
            if (.not. on_board(side, q, r)) cycle
            if (stones(q + side, r + side) /= colour) cycle
            if (taken(q + side, r + side)) cycle

            ! Collect the whole connected group of this colour.
            top = 1
            stack(1, 1) = q
            stack(2, 1) = r
            taken(q + side, r + side) = .true.
            nstone = 0
            do while (top > 0)
               nq = stack(1, top)
               nr = stack(2, top)
               top = top - 1
               nstone = nstone + 1
               group(1, nstone) = nq
               group(2, nstone) = nr
               do k = 1, 6
                  if (.not. on_board(side, nq + dir_q(k), nr + dir_r(k))) cycle
                  if (stones(nq + dir_q(k) + side, nr + dir_r(k) + side) /= colour) cycle
                  if (taken(nq + dir_q(k) + side, nr + dir_r(k) + side)) cycle
                  taken(nq + dir_q(k) + side, nr + dir_r(k) + side) = .true.
                  top = top + 1
                  stack(1, top) = nq + dir_q(k)
                  stack(2, top) = nr + dir_r(k)
               end do
            end do

            corners = 0
            bits = 0
            member = .false.
            do i = 1, nstone
               member(group(1, i) + side, group(2, i) + side) = .true.
               if (is_corner(side, group(1, i), group(2, i))) then
                  corners = corners + 1
               else
                  bits = ior(bits, edge_bits(side, group(1, i), group(2, i)))
               end if
            end do

            if (corners >= 2) any_bridge = .true.
            if (popcnt(bits) >= 3) any_fork = .true.
            if (shuts_in(side, member)) any_ring = .true.
         end do
      end do

      if (any_bridge) then
         code = HAV_BRIDGE
      else if (any_fork) then
         code = HAV_FORK
      else if (any_ring) then
         code = HAV_RING
      else
         code = HAV_NONE
      end if
   end function verdict_for

end module havannah_judge
