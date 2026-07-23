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

   integer function verdict_for(side, stones, colour) result(code)
      ! Answers which shape, if any, the given colour has already finished.
      integer, intent(in) :: side
      character, intent(in) :: stones(:, :)
      character, intent(in) :: colour

      ! The shapes are not worked out yet, so nothing ever reads as a win.
      code = HAV_NONE
   end function verdict_for

end module havannah_judge
