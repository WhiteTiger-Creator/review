program hexverdict
   ! Reads one instance document, hands the position to the judge, and prints a
   ! single line saying whether the named player has already won.
   !
   ! Usage: hexverdict <instance.json>
   !
   ! The document carries "size", the side length of the hexagon, "player",
   ! either "A" or "B", and "cells", a map from "q,r" to the stone standing on
   ! that point. Points left out of the map are empty. The line printed is an
   ! object with a "win" flag and a "type" naming the shape, or null.
   !
   ! Reading, checking and printing are all in place here. What settles the
   ! verdict lives in src/judge.f90 and currently answers no win for every
   ! position; the shapes it has to recognise are written up in docs/rules.md.
   use, intrinsic :: iso_fortran_env, only: error_unit
   use havannah_judge, only: HAV_BRIDGE, HAV_FORK, HAV_RING, on_board, verdict_for
   implicit none

   character(len=:), allocatable :: doc
   character(len=:), allocatable :: path
   character, allocatable :: stones(:, :)
   character :: player
   integer :: arglen
   integer :: side
   integer :: span
   integer :: pos
   integer :: code

   if (command_argument_count() /= 1) then
      write (error_unit, '(a)') 'usage: hexverdict <instance.json>'
      stop 2
   end if

   call get_command_argument(1, length=arglen)
   allocate (character(len=arglen) :: path)
   call get_command_argument(1, value=path)

   call read_whole_file(path, doc)

   pos = after_key(doc, 'size')
   if (pos == 0) call fail('malformed instance')
   side = read_int(doc, pos)

   pos = after_key(doc, 'player')
   if (pos == 0) call fail('malformed instance')
   if (pos + 2 > len(doc)) call fail('malformed instance')
   if (doc(pos:pos) /= '"' .or. doc(pos + 2:pos + 2) /= '"') call fail('malformed instance')
   player = doc(pos + 1:pos + 1)

   if (side < 2 .or. (player /= 'A' .and. player /= 'B')) call fail('bad size or player')

   span = 2*side - 1
   allocate (stones(span, span))
   stones = '.'

   call read_cells(doc, side, stones)

   code = verdict_for(side, stones, player)

   if (code == HAV_BRIDGE) then
      write (*, '(a)') '{"win":true,"type":"bridge"}'
   else if (code == HAV_FORK) then
      write (*, '(a)') '{"win":true,"type":"fork"}'
   else if (code == HAV_RING) then
      write (*, '(a)') '{"win":true,"type":"ring"}'
   else
      write (*, '(a)') '{"win":false,"type":null}'
   end if

contains

   subroutine fail(msg)
      character(len=*), intent(in) :: msg
      write (error_unit, '(a,a)') 'error: ', msg
      stop 1
   end subroutine fail

   subroutine read_whole_file(name, text)
      character(len=*), intent(in) :: name
      character(len=:), allocatable, intent(out) :: text
      integer :: unit
      integer :: ios
      integer :: nbytes
      logical :: there

      inquire (file=name, exist=there, size=nbytes)
      if (.not. there .or. nbytes < 0) call fail('cannot open instance')
      open (newunit=unit, file=name, access='stream', form='unformatted', &
            status='old', action='read', iostat=ios)
      if (ios /= 0) call fail('cannot open instance')
      allocate (character(len=nbytes) :: text)
      if (nbytes > 0) then
         read (unit, iostat=ios) text
         if (ios /= 0) call fail('cannot open instance')
      end if
      close (unit)
   end subroutine read_whole_file

   integer function skip_ws(text, from) result(at)
      ! First index at or after `from` holding something other than blank space.
      character(len=*), intent(in) :: text
      integer, intent(in) :: from
      at = from
      do while (at <= len(text))
         if (iachar(text(at:at)) > iachar(' ')) exit
         at = at + 1
      end do
   end function skip_ws

   integer function after_key(text, key) result(at)
      ! First index of the value that follows "key": , or 0 when absent.
      character(len=*), intent(in) :: text
      character(len=*), intent(in) :: key
      character(len=:), allocatable :: pat
      integer :: from
      integer :: hit
      integer :: colon

      pat = '"'//key//'"'
      at = 0
      from = 1
      do
         hit = index(text(from:), pat)
         if (hit == 0) return
         hit = from + hit - 1
         colon = skip_ws(text, hit + len(pat))
         if (colon <= len(text)) then
            if (text(colon:colon) == ':') then
               at = skip_ws(text, colon + 1)
               return
            end if
         end if
         from = hit + 1
      end do
   end function after_key

   integer function read_int(text, from) result(value)
      ! Reads a signed decimal starting at `from`, refusing an empty run.
      character(len=*), intent(in) :: text
      integer, intent(in) :: from
      integer :: last
      integer :: ios

      last = from
      if (last <= len(text)) then
         if (text(last:last) == '-' .or. text(last:last) == '+') last = last + 1
      end if
      if (last > len(text)) call fail('malformed instance')
      if (text(last:last) < '0' .or. text(last:last) > '9') call fail('malformed instance')
      do while (last <= len(text))
         if (text(last:last) < '0' .or. text(last:last) > '9') exit
         last = last + 1
      end do
      read (text(from:last - 1), *, iostat=ios) value
      if (ios /= 0) call fail('malformed instance')
   end function read_int

   subroutine read_pair(key, q, r)
      ! Splits "<int>,<int>" apart, refusing anything with leftovers.
      character(len=*), intent(in) :: key
      integer, intent(out) :: q
      integer, intent(out) :: r
      integer :: comma
      integer :: ios

      comma = index(key, ',')
      if (comma <= 1 .or. comma >= len(key)) call fail('bad cell key')
      read (key(1:comma - 1), *, iostat=ios) q
      if (ios /= 0) call fail('bad cell key')
      read (key(comma + 1:), *, iostat=ios) r
      if (ios /= 0) call fail('bad cell key')
   end subroutine read_pair

   subroutine read_cells(text, n, board)
      character(len=*), intent(in) :: text
      integer, intent(in) :: n
      character, intent(inout) :: board(:, :)
      integer :: at
      integer :: kend
      integer :: vend
      integer :: q
      integer :: r

      at = after_key(text, 'cells')
      if (at == 0) return
      if (text(at:at) /= '{') call fail('malformed instance')
      at = at + 1
      do
         at = skip_ws(text, at)
         if (at > len(text)) exit
         if (text(at:at) == '}') exit
         if (text(at:at) == ',') then
            at = at + 1
            cycle
         end if
         if (text(at:at) /= '"') call fail('malformed instance')
         kend = index(text(at + 1:), '"')
         if (kend == 0) call fail('malformed instance')
         kend = at + kend
         call read_pair(text(at + 1:kend - 1), q, r)

         at = skip_ws(text, kend + 1)
         if (at > len(text)) call fail('malformed instance')
         if (text(at:at) /= ':') call fail('malformed instance')
         at = skip_ws(text, at + 1)
         if (at > len(text)) call fail('malformed instance')
         if (text(at:at) /= '"') call fail('malformed instance')
         vend = index(text(at + 1:), '"')
         if (vend == 0) call fail('malformed instance')
         vend = at + vend
         if (vend - at /= 2) call fail('bad stone')
         if (text(at + 1:at + 1) /= 'A' .and. text(at + 1:at + 1) /= 'B') call fail('bad stone')
         if (.not. on_board(n, q, r)) call fail('cell off board')
         board(q + n, r + n) = text(at + 1:at + 1)
         at = vend + 1
      end do
   end subroutine read_cells

end program hexverdict
